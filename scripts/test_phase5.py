#!/usr/bin/env python3
"""Phase 5 hardening test: min-bet floor, login throttle, concurrency/overspend safety,
and reconciliation (ledger <-> bank).

Prereqs: bank up + FRESH seed (bettor1 at 100), our API up (:8010), app DB reset.
    ./.venv/bin/python scripts/test_phase5.py
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import httpx
import pyotp

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

API = "http://127.0.0.1:8010"
ADMIN = {"X-Admin-Key": "dev-admin-key"}
BETTOR_PAN, TOTP = "8997000000000001", "JBSWY3DPEHPK3PXP"

PASS, FAIL = "\033[32mPASS\033[0m", "\033[31mFAIL\033[0m"
_fail = 0


def check(label, got, want):
    global _fail
    ok = got == want
    _fail += 0 if ok else 1
    print(f"  [{PASS if ok else FAIL}] {label}: got {got!r}, want {want!r}")


async def main() -> int:
    async with httpx.AsyncClient(base_url=API, timeout=30) as api:
        # A. Login throttle (fake card so we don't burn the real bettor's bank OTP limit)
        print("1. Login throttle")
        statuses = []
        for _ in range(10):
            r = await api.post("/api/auth/login", json={"pan": "0000000000000000", "otp": "000000"})
            statuses.append(r.status_code)
        check("early attempt rejected 401", statuses[0], 401)
        check("throttled to 429 within 10", 429 in statuses, True)

        # B. Fund a wallet
        print("2. Login + deposit 100")
        r = await api.post("/api/auth/login", json={"pan": BETTOR_PAN, "otp": pyotp.TOTP(TOTP).now()})
        r.raise_for_status()
        hdr = {"Authorization": f"Bearer {r.json()['session_token']}"}
        r = await api.post("/api/wallet/deposit", json={"amount_cents": 10000, "idempotency_key": "p5-dep-0001"}, headers=hdr)
        r.raise_for_status()
        check("wallet 10000", r.json()["wallet"]["balance_cents"], 10000)

        # Market
        r = await api.post("/api/admin/markets", headers=ADMIN, json={"title": "P5", "outcomes": ["Yes", "No"]})
        r.raise_for_status()
        m = r.json()
        mid, yes = m["id"], next(o["id"] for o in m["outcomes"] if o["label"] == "Yes")

        # C. Min-bet floor (10 bucks = 1000c)
        print("3. Min-bet floor")
        r = await api.post(f"/api/markets/{mid}/bet", headers=hdr,
                           json={"outcome_id": yes, "stake_cents": 500, "idempotency_key": "p5-low-0001"})
        check("below min -> 400", r.status_code, 400)
        r = await api.post(f"/api/markets/{mid}/bet", headers=hdr,
                           json={"outcome_id": yes, "stake_cents": 1000, "idempotency_key": "p5-min-0001"})
        check("exactly min -> ok", r.status_code, 200)  # wallet now 9000

        # D. Concurrency / overspend safety: 20 simultaneous 1000c bets, only 9 can fit in 9000
        print("4. Concurrency / overspend safety (20 parallel bets, wallet=9000)")
        async def fire(i):
            return await api.post(f"/api/markets/{mid}/bet", headers=hdr,
                                  json={"outcome_id": yes, "stake_cents": 1000, "idempotency_key": f"p5-conc-{i:04d}"})
        results = await asyncio.gather(*[fire(i) for i in range(20)])
        codes = [r.status_code for r in results]
        successes = codes.count(200)
        check("exactly 9 succeed", successes, 9)
        check("rest rejected 402", codes.count(402), 11)
        wallet = (await api.get("/api/wallet", headers=hdr)).json()["balance_cents"]
        check("wallet drained to 0 (no overspend)", wallet, 0)
        pool_total = (await api.get(f"/api/markets/{mid}")).json()["total_pool_cents"]
        check("pool == staked (1000 + 9*1000)", pool_total, 10000)

        # E. Reconciliation
        print("5. Reconcile ledger <-> bank")
        rec = (await api.get("/api/admin/reconcile", headers=ADMIN)).json()
        check("reconcile ok", rec["ok"], True)
        check("no missing at bank", rec["missing_at_bank"], [])
        check("no negative wallets", rec["negative_wallets"], [])
        check("money balanced", rec["money_balanced"], True)
        check("net in system 10000", rec["net_in_system_cents"], 10000)

    print()
    print(f"RESULT: {FAIL if _fail else PASS}" + (f" — {_fail} failed" if _fail else " — Phase 5 verified"))
    return 1 if _fail else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
