"""End-of-event cash-out: pay every wallet back to its card via the bank.

For each user with a positive wallet balance we (1) record a durable CashOut row, (2) PUSH
the bucks from the house account to the user's card via the house token, then (3) debit the
wallet in our ledger and mark SENT. A failure marks FAILED with the error; the wallet is left
untouched so it can be retried. (Phase 5 will add rate-limit-aware batching + retry.)
"""
from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import ledger, security
from app.house import house_login
from app.models import CashOut, CashoutStatus, TxType, User
from bank import ShadyBankClient, ShadyBankError


async def run_cashout(db: AsyncSession, bank: ShadyBankClient, otp: str | None = None) -> dict:
    house_token = await house_login(bank, otp)  # live: admin-supplied OTP; dev: PIN fallback
    external = await ledger.get_system_account(db, "EXTERNAL")

    users = (await db.execute(select(User))).scalars().all()
    sent_count = failed_count = sent_cents = 0
    failures: list[dict] = []

    for user in users:
        bal = await ledger.balance_cents(db, user.ledger_account_id)
        if bal <= 0:
            continue

        co = CashOut(user_id=user.id, amount_cents=bal, status=CashoutStatus.PENDING)
        db.add(co)
        await db.commit()  # durable before the bank call

        try:
            await bank.credit(
                house_token, Decimal(bal) / 100,
                pan=security.decrypt(user.pan_enc), description=f"sp:cashout:{co.id}",
            )
        except ShadyBankError as e:
            co.status = CashoutStatus.FAILED
            co.error = (e.body or str(e))[:255]
            await db.commit()
            failed_count += 1
            failures.append({"user_id": str(user.id), "amount_cents": bal, "error": co.error})
            continue

        tx = await ledger.post_tx(db, TxType.CASHOUT,
                                  entries=[(user.ledger_account_id, external.id, bal)],
                                  meta={"cashout_id": str(co.id)})
        co.tx_id = tx.id
        co.status = CashoutStatus.SENT
        await db.commit()
        sent_count += 1
        sent_cents += bal

    return {"sent_count": sent_count, "failed_count": failed_count,
            "sent_cents": sent_cents, "failures": failures}
