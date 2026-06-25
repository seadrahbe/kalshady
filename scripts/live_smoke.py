#!/usr/bin/env python3
"""READ-ONLY smoke test against the LIVE shadybank (bucks.shady.tel).

Confirms our ShadyBankClient works against the real instance: login -> balance ->
transactions. It makes NO money-moving calls (no authorize/capture/credit). Safe to run
against your real account.

Credentials are read from the environment (or a gitignored `.env.live` file) so they stay
out of the chat transcript. Because an OTP expires in ~30s, the simplest is to pass a fresh
OTP on the command line while keeping your card number in .env.live:

    # one-time, in YOUR terminal (not pasted into chat):
    printf 'LIVE_PAN=8997xxxxxxxxxxxx\n' > .env.live      # .env.live is gitignored

    # then, with a fresh code from your authenticator:
    ! LIVE_OTP=123456 ./.venv/bin/python scripts/live_smoke.py

You can also use LIVE_PIN=... instead of LIVE_OTP if your account has a PIN.
"""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from bank import ShadyBankClient, ShadyBankError  # noqa: E402


def _load_env_live() -> None:
    f = ROOT / ".env.live"
    if not f.exists():
        return
    for line in f.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())


def _mask(pan: str) -> str:
    return pan[:4] + "*" * max(0, len(pan) - 8) + pan[-4:] if len(pan) >= 8 else "****"


async def main() -> int:
    _load_env_live()
    url = os.environ.get("LIVE_API_URL", "https://bucks.shady.tel")
    pan = os.environ.get("LIVE_PAN")
    otp = os.environ.get("LIVE_OTP")
    pin = os.environ.get("LIVE_PIN")
    account_id = os.environ.get("LIVE_ACCOUNT_ID")

    if not (pan or account_id) or not (otp or pin):
        print("Missing creds. Set LIVE_PAN (or LIVE_ACCOUNT_ID) and LIVE_OTP (or LIVE_PIN). "
              "See the header of this file.")
        return 2

    print(f"Target: {url}  (READ-ONLY: login -> balance -> transactions)")
    async with ShadyBankClient(url) as bank:
        try:
            token = await bank.login(
                pan=pan, account_id=int(account_id) if account_id else None, otp=otp, pin=pin
            )
        except ShadyBankError as e:
            print(f"LOGIN FAILED: {e}")
            return 1
        print(f"  login OK ({'OTP' if otp else 'PIN'}) for card {_mask(pan or '')}")

        bal = await bank.balance(token)
        print(f"  balance: account={bal['account']} name={bal['name']!r} "
              f"balance={bal['balance']} available={bal['available']}")

        txns = await bank.transactions(token)
        print(f"  transactions: {len(txns)} found"
              + (f" (latest: {txns[0]['type']} {txns[0]['amount']} <-> {txns[0]['counterparty']})" if txns else ""))

        await bank.logout(token)
    print("\nPASS: our client works against the LIVE shadybank (read-only).")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
