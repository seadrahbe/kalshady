#!/usr/bin/env python3
"""Phase 2 acceptance test: markets, parimutuel betting, live odds, positions.

Prereqs: bank up+seeded, our API up (:8010), app DB reset.
    ./.venv/bin/python scripts/test_markets.py
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import httpx
import pyotp

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

API = "http://127.0.0.1:8010"
ADMIN_KEY = "dev-admin-key"
BETTOR_PAN, BETTOR_TOTP = "8997000000000001", "JBSWY3DPEHPK3PXP"

PASS, FAIL = "\033[32mPASS\033[0m", "\033[31mFAIL\033[0m"
_fail = 0


def check(label, got, want):
    global _fail
    ok = got == want
    if not ok:
        _fail += 1
    print(f"  [{PASS if ok else FAIL}] {label}: got {got!r}, want {want!r}")


def price(market, label):
    return next(o["price_cents"] for o in market["outcomes"] if o["label"] == label)


def oid(market, label):
    return next(o["id"] for o in market["outcomes"] if o["label"] == label)


async def main() -> int:
    async with httpx.AsyncClient(base_url=API, timeout=15) as api:
        admin = {"X-Admin-Key": ADMIN_KEY}

        # 0. Admin auth enforced
        r = await api.post("/api/admin/markets", json={"title": "x", "outcomes": ["a", "b"]},
                           headers={"X-Admin-Key": "wrong"})
        check("bad admin key -> 403", r.status_code, 403)

        # 1. Create a market
        print("1. Admin creates market")
        r = await api.post("/api/admin/markets", headers=admin, json={
            "title": "Will it rain at ToorCamp?", "outcomes": ["Yes", "No"], "rake_bps": 0,
        })
        r.raise_for_status()
        market = r.json()
        mid = market["id"]
        check("two outcomes", len(market["outcomes"]), 2)
        check("even odds before bets (Yes)", price(market, "Yes"), 50)

        # 2. Bettor signs in and funds wallet
        print("2. Bettor login + deposit 50")
        totp = pyotp.TOTP(BETTOR_TOTP)
        r = await api.post("/api/auth/login", json={"pan": BETTOR_PAN, "otp": totp.now()})
        r.raise_for_status()
        hdr = {"Authorization": f"Bearer {r.json()['session_token']}"}
        r = await api.post("/api/wallet/deposit",
                           json={"amount_cents": 5000, "idempotency_key": "mkt-dep-0001"}, headers=hdr)
        r.raise_for_status()
        check("wallet funded 5000", r.json()["wallet"]["balance_cents"], 5000)

        yes, no = oid(market, "Yes"), oid(market, "No")

        # 3. Bet 30 on Yes, 10 on No -> 75/25 odds
        print("3. Bet 30 Yes, 10 No")
        r = await api.post(f"/api/markets/{mid}/bet", headers=hdr,
                           json={"outcome_id": yes, "stake_cents": 3000, "idempotency_key": "bet-yes-0001"})
        r.raise_for_status()
        check("wallet after Yes bet 2000", r.json()["wallet"]["balance_cents"], 2000)
        r = await api.post(f"/api/markets/{mid}/bet", headers=hdr,
                           json={"outcome_id": no, "stake_cents": 1000, "idempotency_key": "bet-no-0001"})
        r.raise_for_status()
        m = r.json()["market"]
        check("wallet after No bet 1000", r.json()["wallet"]["balance_cents"], 1000)
        check("Yes price 75", price(m, "Yes"), 75)
        check("No price 25", price(m, "No"), 25)
        check("total pool 4000", m["total_pool_cents"], 4000)

        # 4. Live odds via public GET
        r = await api.get(f"/api/markets/{mid}")
        check("public odds Yes 75", price(r.json(), "Yes"), 75)

        # 5. Position + projected payout (rake 0, single bettor -> whole pool back)
        print("4. Position")
        r = await api.get(f"/api/markets/{mid}/position", headers=hdr)
        pos = {p["label"]: p for p in r.json()["positions"]}
        check("Yes stake 3000", pos["Yes"]["stake_cents"], 3000)
        check("Yes projected 4000", pos["Yes"]["projected_payout_cents"], 4000)

        # 6. Idempotent bet (same key -> no extra charge)
        print("5. Idempotency + guards")
        r = await api.post(f"/api/markets/{mid}/bet", headers=hdr,
                           json={"outcome_id": yes, "stake_cents": 3000, "idempotency_key": "bet-yes-0001"})
        r.raise_for_status()
        check("still 1000 (idempotent)", r.json()["wallet"]["balance_cents"], 1000)

        # 7. Insufficient funds
        r = await api.post(f"/api/markets/{mid}/bet", headers=hdr,
                           json={"outcome_id": yes, "stake_cents": 9_999_999, "idempotency_key": "bet-huge-0001"})
        check("overspend -> 402", r.status_code, 402)

        # 8. Closed market rejects bets
        r = await api.post(f"/api/admin/markets/{mid}/close", headers=admin)
        r.raise_for_status()
        check("market closed", r.json()["status"], "CLOSED")
        r = await api.post(f"/api/markets/{mid}/bet", headers=hdr,
                           json={"outcome_id": yes, "stake_cents": 100, "idempotency_key": "bet-closed-0001"})
        check("bet on closed -> 409", r.status_code, 409)

    print()
    print(f"RESULT: {FAIL if _fail else PASS}" + (f" — {_fail} failed" if _fail else " — Phase 2 verified"))
    return 1 if _fail else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
