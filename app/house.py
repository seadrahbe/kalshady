"""Log in as the house (merchant) account at the bank.

On the live bank the house secret is a 30s TOTP the admin supplies at cash-out time, so we
prefer an `otp` passed in at runtime. For local dev/tests the house has a static PIN, used as
a fallback when no OTP is given.
"""
from __future__ import annotations

from app.config import get_settings
from bank import ShadyBankClient


async def house_login(bank: ShadyBankClient, otp: str | None = None) -> str:
    s = get_settings()
    if otp:
        return await bank.login(pan=s.house_pan, otp=otp)
    return await bank.login(pan=s.house_pan, pin=s.house_pin)
