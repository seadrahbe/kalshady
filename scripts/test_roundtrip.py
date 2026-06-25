#!/usr/bin/env python3
"""Phase 0 acceptance test: prove the deposit -> cash-out round-trip against a
locally running shadybank.

Flow (mirrors ShadyPredict's only two bank interactions):
  1. Customer logs in with PAN + OTP, reads balance.
  2. House (merchant) logs in with PAN + PIN.
  3. Deposit: house authorize()s + capture()s 10 bucks off the customer's card.
  4. Verify customer -10, house +10.
  5. Cash-out: house credit()s the 10 bucks back to the customer's card.
  6. Verify balances returned to start.

Run shadybank first (docker compose up) and load seed.sql, then:
    ./.venv/bin/python scripts/test_roundtrip.py
"""

from __future__ import annotations

import asyncio
import sys
from decimal import Decimal
from pathlib import Path

import pyotp

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from bank import ShadyBankClient, ShadyBankError  # noqa: E402

BASE_URL = "http://127.0.0.1:8021"

BETTOR_PAN = "8997000000000001"
BETTOR_TOTP_SECRET = "JBSWY3DPEHPK3PXP"
HOUSE_PAN = "8997000000000002"
HOUSE_PIN = "4242"

DEPOSIT = Decimal("10.00")

PASS, FAIL = "\033[32mPASS\033[0m", "\033[31mFAIL\033[0m"
_failures = 0


def check(label: str, got, want) -> None:
    global _failures
    ok = got == want
    if not ok:
        _failures += 1
    print(f"  [{PASS if ok else FAIL}] {label}: got {got!r}, want {want!r}")


async def main() -> int:
    totp = pyotp.TOTP(BETTOR_TOTP_SECRET)

    async with ShadyBankClient(BASE_URL) as bank:
        # 1. Customer login + starting balance ------------------------------
        print("1. Customer login (PAN + OTP)")
        cust_token = await bank.login(pan=BETTOR_PAN, otp=totp.now())
        cust = await bank.balance(cust_token)
        print(f"   bettor account={cust['account']} name={cust['name']!r} balance={cust['balance']}")
        start_bettor = Decimal(str(cust["balance"]))
        check("bettor starts funded", start_bettor, Decimal("100.00"))

        # 2. House login ----------------------------------------------------
        print("2. House login (PAN + PIN)")
        house_token = await bank.login(pan=HOUSE_PAN, pin=HOUSE_PIN)
        house = await bank.balance(house_token)
        print(f"   house account={house['account']} name={house['name']!r} balance={house['balance']}")
        start_house = Decimal(str(house["balance"]))

        # 3. Deposit: authorize + capture -----------------------------------
        print(f"3. Deposit {DEPOSIT} (authorize + capture)")
        auth_code = await bank.authorize(house_token, DEPOSIT, pan=BETTOR_PAN, otp=totp.now(),
                                         description="ShadyPredict deposit")
        print(f"   auth_code={auth_code}")
        await bank.capture(house_token, auth_code, DEPOSIT, description="ShadyPredict deposit")

        # 4. Verify the deposit moved the money -----------------------------
        bettor_after = Decimal(str((await bank.balance(cust_token))["balance"]))
        house_after = Decimal(str((await bank.balance(house_token))["balance"]))
        print(f"   after deposit: bettor={bettor_after} house={house_after}")
        check("bettor debited", bettor_after, start_bettor - DEPOSIT)
        check("house credited", house_after, start_house + DEPOSIT)

        # 5. Cash-out: credit back ------------------------------------------
        print(f"5. Cash-out {DEPOSIT} (credit back to card)")
        await bank.credit(house_token, DEPOSIT, pan=BETTOR_PAN, description="ShadyPredict cash-out")

        # 6. Verify we're back to start -------------------------------------
        bettor_final = Decimal(str((await bank.balance(cust_token))["balance"]))
        house_final = Decimal(str((await bank.balance(house_token))["balance"]))
        print(f"   final: bettor={bettor_final} house={house_final}")
        check("bettor restored", bettor_final, start_bettor)
        check("house restored", house_final, start_house)

        # Bonus: transaction history shows the two entries
        txns = await bank.transactions(cust_token)
        print(f"   bettor transaction history: {len(txns)} entries")
        for t in txns:
            print(f"     {t['type']:6} {t['amount']:>7} {t['subtype']:13} <-> {t['counterparty']}")

    print()
    if _failures:
        print(f"RESULT: {FAIL} — {_failures} check(s) failed")
        return 1
    print(f"RESULT: {PASS} — deposit -> cash-out round-trip verified end to end")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(asyncio.run(main()))
    except ShadyBankError as e:
        print(f"\nBANK ERROR: {e}")
        raise SystemExit(2)
