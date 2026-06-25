from __future__ import annotations

from datetime import datetime, timezone

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_db
from app.models import Session, User
from bank import ShadyBankClient


def get_bank(request: Request) -> ShadyBankClient:
    return request.app.state.bank


def _extract_token(request: Request) -> str | None:
    # Prefer Authorization: Bearer <token> (SPA on another origin); fall back to cookie.
    auth = request.headers.get("Authorization", "")
    parts = auth.split(" ", 1)
    if len(parts) == 2 and parts[0].lower() == "bearer" and parts[1]:
        return parts[1].strip()
    return request.cookies.get(get_settings().cookie_name)


async def get_current_session(
    request: Request, db: AsyncSession = Depends(get_db)
) -> Session:
    token = _extract_token(request)
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "not signed in")
    session = await db.get(Session, token)
    if not session or session.revoked:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid session")
    if session.expires_at <= datetime.now(timezone.utc):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "session expired")
    return session


def require_admin(request: Request) -> None:
    key = request.headers.get("X-Admin-Key", "")
    if key != get_settings().admin_key:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "admin key required")


async def get_current_user(
    session: Session = Depends(get_current_session), db: AsyncSession = Depends(get_db)
) -> User:
    user = await db.get(User, session.user_id)
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "user not found")
    return user
