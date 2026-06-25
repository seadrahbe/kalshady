from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import ledger, ratelimit, security
from app.config import get_settings
from app.db import get_db
from app.deps import get_bank, get_current_session, get_current_user
from app.models import Session, User
from app.schemas import LoginRequest, LoginResponse, MeResponse, UserOut, WalletOut, cents_to_display
from bank import ShadyBankClient, ShadyBankError

router = APIRouter(prefix="/api/auth", tags=["auth"])


async def _me_payload(db: AsyncSession, user: User) -> dict:
    bal = await ledger.balance_cents(db, user.ledger_account_id)
    return {
        "user": UserOut(id=user.id, name=user.name, shadybank_account_id=user.shadybank_account_id),
        "wallet": WalletOut(balance_cents=bal, balance_display=cents_to_display(bal)),
    }


@router.post("/login", response_model=LoginResponse)
async def login(
    body: LoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
    bank: ShadyBankClient = Depends(get_bank),
) -> LoginResponse:
    """Sign in with ShadyBucks (PAN + OTP). We verify against the bank, keep the bank token
    server-side (encrypted) for PUSH deposits, and issue our own session token."""
    settings = get_settings()
    # Our own login throttle (the bank does not rate-limit PIN/password).
    if not ratelimit.allow(f"login:{body.pan}", settings.login_max_attempts, settings.login_window_seconds):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "too many login attempts; wait a bit")
    try:
        bank_token = await bank.login(pan=body.pan, otp=body.otp)
        info = await bank.balance(bank_token)
    except ShadyBankError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "ShadyBucks login failed")

    account_id = int(info["account"])
    name = info.get("name") or "Bettor"

    user = (
        await db.execute(select(User).where(User.shadybank_account_id == account_id))
    ).scalar_one_or_none()
    if user is None:
        wallet = await ledger.create_user_wallet(db, user_id=None)  # set user_id after we have the user id
        user = User(
            shadybank_account_id=account_id,
            name=name,
            pan_enc=security.encrypt(body.pan),
            ledger_account_id=wallet.id,
        )
        db.add(user)
        await db.flush()
        wallet.user_id = user.id
    else:
        user.name = name
        user.pan_enc = security.encrypt(body.pan)

    token = security.new_session_token()
    db.add(Session(
        id=token,
        user_id=user.id,
        bank_token_enc=security.encrypt(bank_token),
        expires_at=datetime.now(timezone.utc) + timedelta(seconds=settings.session_ttl_seconds),
    ))
    await db.commit()

    response.set_cookie(
        settings.cookie_name, token, max_age=settings.session_ttl_seconds,
        httponly=True, secure=settings.cookie_secure, samesite="lax",
    )
    payload = await _me_payload(db, user)
    return LoginResponse(session_token=token, **payload)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    response: Response,
    session: Session = Depends(get_current_session),
    db: AsyncSession = Depends(get_db),
) -> Response:
    session.revoked = True
    await db.commit()
    response.delete_cookie(get_settings().cookie_name)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me", response_model=MeResponse)
async def me(
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> MeResponse:
    return MeResponse(**await _me_payload(db, user))
