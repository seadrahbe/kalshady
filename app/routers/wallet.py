from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app import ledger, security
from app.config import get_settings
from app.db import get_db
from app.deps import get_bank, get_current_session, get_current_user
from app.models import Deposit, DepositStatus, Session, TxType, User
from app.schemas import DepositRequest, DepositResponse, WalletOut, cents_to_display
from bank import ShadyBankClient, ShadyBankError

router = APIRouter(prefix="/api/wallet", tags=["wallet"])


async def _wallet_out(db: AsyncSession, user: User) -> WalletOut:
    bal = await ledger.balance_cents(db, user.ledger_account_id)
    return WalletOut(balance_cents=bal, balance_display=cents_to_display(bal))


@router.get("", response_model=WalletOut)
async def get_wallet(
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> WalletOut:
    return await _wallet_out(db, user)


@router.post("/deposit", response_model=DepositResponse)
async def deposit(
    body: DepositRequest,
    session: Session = Depends(get_current_session),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    bank: ShadyBankClient = Depends(get_bank),
) -> DepositResponse:
    """PUSH deposit: move bucks from the bettor's bank account into their wallet using the
    bettor's own (server-side) bank token — no OTP. Idempotent on `idempotency_key`."""
    # 1. Idempotency: return any prior result for this key instead of charging again.
    existing = (
        await db.execute(select(Deposit).where(Deposit.idempotency_key == body.idempotency_key))
    ).scalar_one_or_none()
    if existing is not None:
        if existing.status == DepositStatus.FAILED:
            raise HTTPException(status.HTTP_402_PAYMENT_REQUIRED, existing.error or "previous deposit failed")
        return DepositResponse(
            deposit_id=existing.id, status=existing.status.value, wallet=await _wallet_out(db, user)
        )

    # 2. Create a durable PENDING row before touching the bank (crash-safe + reconcilable).
    dep = Deposit(
        user_id=user.id,
        amount_cents=body.amount_cents,
        idempotency_key=body.idempotency_key,
        bank_description="",  # filled below once we have the id
    )
    db.add(dep)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        # Lost an idempotency-key race; return the winner's state.
        existing = (
            await db.execute(select(Deposit).where(Deposit.idempotency_key == body.idempotency_key))
        ).scalar_one()
        return DepositResponse(
            deposit_id=existing.id, status=existing.status.value, wallet=await _wallet_out(db, user)
        )
    dep.bank_description = f"sp:deposit:{dep.id}"
    await db.commit()

    # 3. Move the money at the bank (PUSH: user's token -> house PAN). No OTP.
    settings = get_settings()
    bank_token = security.decrypt(session.bank_token_enc)
    try:
        await bank.credit(
            bank_token, Decimal(body.amount_cents) / 100,
            pan=settings.house_pan, description=dep.bank_description,
        )
    except ShadyBankError as e:
        dep.status = DepositStatus.FAILED
        dep.error = (e.body or str(e))[:255]
        await db.commit()
        raise HTTPException(status.HTTP_402_PAYMENT_REQUIRED,
                            "deposit declined by the bank (insufficient funds?)")

    # 4. Credit the wallet in our ledger (EXTERNAL -> user wallet) and mark confirmed.
    external = await ledger.get_system_account(db, "EXTERNAL")
    tx = await ledger.post_tx(
        db, TxType.DEPOSIT,
        entries=[(external.id, user.ledger_account_id, body.amount_cents)],
        meta={"deposit_id": str(dep.id)},
    )
    dep.tx_id = tx.id
    dep.status = DepositStatus.CONFIRMED
    await db.commit()

    return DepositResponse(deposit_id=dep.id, status=dep.status.value, wallet=await _wallet_out(db, user))
