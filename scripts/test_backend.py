#!/usr/bin/env python3
"""Phase 1 acceptance test for the ShadyPredict backend.

Exercises the real API (sign-in + PUSH deposit + idempotency) and cross-checks the
money actually moved at the bank.

Prereqs: shadybank up (:8021) and seeded (seed.sql), our API up (:8000), our DB up (:5433).
    ./.venv/bin/python scripts/test_backend.py
"""
from __future__ import annotations

import asyncio
import sys
from decimal import Decimal
from pathlib import Path

import httpx
import pyotp

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from bank import ShadyBankClient  # noqa: E402

API = "http://127.0.0.1:8010"
BANK = "http://127.0.0.1:8021"
BETTOR_PAN, BETTOR_TOTP = "8997000000000001", "JBSWY3DPEHPK3PXP"
HOUSE_PAN, HOUSE_PIN = "8997000000000002", "4242"

PASS, FAIL = "\033[32mPASS\033[0m", "\033[31mFAIL\033[0m"
_fail = 0


def check(label, got, want):
    global _fail
    ok = got == want
    if not ok:
        _fail += 1
    print(f"  [{PASS if ok else FAIL}] {label}: got {got!r}, want {want!r}")


async def bank_balance(bank, *, pan=None, pin=None, otp=None) -> Decimal:
    token = await bank.login(pan=pan, otp=otp, pin=pin)
    return Decimal(str((await bank.balance(token))["balance"]))


async def main() -> int:
    totp = pyotp.TOTP(BETTOR_TOTP)
    async with ShadyBankClient(BANK) as bank, httpx.AsyncClient(base_url=API, timeout=15) as api:
        # Read bettor balance via PIN (not OTP) so we don't exhaust the OTP rate limit;
        # OTP is reserved for the one real API login below.
        b_start = await bank_balance(bank, pan=BETTOR_PAN, pin="1111")
        h_start = await bank_balance(bank, pan=HOUSE_PAN, pin=HOUSE_PIN)
        print(f"bank start: bettor={b_start} house={h_start}")

        # 1. Sign in with ShadyBucks
        print("1. POST /api/auth/login")
        r = await api.post("/api/auth/login", json={"pan": BETTOR_PAN, "otp": totp.now()})
        r.raise_for_status()
        data = r.json()
        token = data["session_token"]
        hdr = {"Authorization": f"Bearer {token}"}
        print(f"   user={data['user']['name']!r} wallet={data['wallet']['balance_display']}")
        check("new wallet starts at 0", data["wallet"]["balance_cents"], 0)

        # 2. PUSH deposit 25.00
        print("2. POST /api/wallet/deposit 2500c")
        r = await api.post("/api/wallet/deposit",
                           json={"amount_cents": 2500, "idempotency_key": "test-deposit-aaaaaaaa"}, headers=hdr)
        r.raise_for_status()
        dep = r.json()
        print(f"   status={dep['status']} wallet={dep['wallet']['balance_display']}")
        check("deposit confirmed", dep["status"], "CONFIRMED")
        check("wallet now 2500", dep["wallet"]["balance_cents"], 2500)

        # 3. GET /api/wallet reflects it
        r = await api.get("/api/wallet", headers=hdr)
        check("GET wallet 2500", r.json()["balance_cents"], 2500)

        # 4. Idempotency: same key -> no double charge
        print("3. POST deposit again, SAME idempotency key")
        r = await api.post("/api/wallet/deposit",
                           json={"amount_cents": 2500, "idempotency_key": "test-deposit-aaaaaaaa"}, headers=hdr)
        r.raise_for_status()
        check("still 2500 (idempotent)", r.json()["wallet"]["balance_cents"], 2500)

        # 5. The money actually moved at the bank
        b_end = await bank_balance(bank, pan=BETTOR_PAN, pin="1111")
        h_end = await bank_balance(bank, pan=HOUSE_PAN, pin=HOUSE_PIN)
        print(f"bank end:   bettor={b_end} house={h_end}")
        check("bettor bank -25", b_end, b_start - Decimal("25.00"))
        check("house bank +25", h_end, h_start + Decimal("25.00"))

        # 6. Auth is enforced (fresh client => no session cookie, no bearer)
        async with httpx.AsyncClient(base_url=API, timeout=15) as anon:
            r = await anon.get("/api/wallet")
        check("no token -> 401", r.status_code, 401)

    print()
    print(f"RESULT: {FAIL if _fail else PASS}" + (f" — {_fail} check(s) failed" if _fail else " — Phase 1 backend verified"))
    return 1 if _fail else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
