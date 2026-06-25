#!/usr/bin/env python3
"""Demonstrates the finding: ANY logged-in user can push shadybucks to another
account via /api/credit -- no merchant flag, no per-transaction OTP.

This is exactly the PUSH deposit model: a bettor logs in once (PAN+OTP) and then
funds their wallet by crediting the house with their own session token.

    bettor --credit(5)--> house    (using the BETTOR's token, no OTP)
"""
from __future__ import annotations

import asyncio
import sys
from decimal import Decimal
from pathlib import Path

import pyotp

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from bank import ShadyBankClient  # noqa: E402

BASE_URL = "http://127.0.0.1:8021"
BETTOR_PAN, BETTOR_TOTP = "8997000000000001", "JBSWY3DPEHPK3PXP"
HOUSE_PAN = "8997000000000002"
AMOUNT = Decimal("5.00")


async def main() -> int:
    async with ShadyBankClient(BASE_URL) as bank:
        # Bettor logs in ONCE with an OTP; we keep their token for the session.
        bettor_token = await bank.login(pan=BETTOR_PAN, otp=pyotp.TOTP(BETTOR_TOTP).now())
        # House token only used to read its balance for the demo.
        house_token = await bank.login(pan=HOUSE_PAN, pin="4242")

        b0 = Decimal(str((await bank.balance(bettor_token))["balance"]))
        h0 = Decimal(str((await bank.balance(house_token))["balance"]))
        print(f"before:  bettor={b0}  house={h0}")

        # The bettor (a normal customer, NOT a merchant) pushes funds to the house
        # PAN using their OWN token. No OTP. No special account flag.
        await bank.credit(bettor_token, AMOUNT, pan=HOUSE_PAN, description="ShadyPredict push deposit")

        b1 = Decimal(str((await bank.balance(bettor_token))["balance"]))
        h1 = Decimal(str((await bank.balance(house_token))["balance"]))
        print(f"after:   bettor={b1}  house={h1}")

        ok = (b1 == b0 - AMOUNT) and (h1 == h0 + AMOUNT)
        print(f"\n{'PASS' if ok else 'FAIL'}: a non-merchant user pushed {AMOUNT} to another "
              f"account with only their login token (no OTP, no merchant flag).")
        return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
