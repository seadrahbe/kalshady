#!/usr/bin/env python3
"""Phase 4 acceptance test: price history, trades ticker, portfolio, and the SSE stream.

Prereqs: bank up (bettor1 funded), our API up (:8010), app DB reset.
    ./.venv/bin/python scripts/test_phase4.py
"""
from __future__ import annotations

import asyncio
import json
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


def price(market, label):
    return next(o["price_cents"] for o in market["outcomes"] if o["label"] == label)


async def main() -> int:
    async with httpx.AsyncClient(base_url=API, timeout=20) as api:
        # Market
        r = await api.post("/api/admin/markets", headers=ADMIN,
                           json={"title": "Phase4 demo", "outcomes": ["Yes", "No"]})
        r.raise_for_status()
        m = r.json()
        mid = m["id"]
        yes = next(o["id"] for o in m["outcomes"] if o["label"] == "Yes")
        no = next(o["id"] for o in m["outcomes"] if o["label"] == "No")

        # History has an initial even-odds point
        print("1. History after create")
        h = (await api.get(f"/api/markets/{mid}/history")).json()
        yes_pts = next(o["points"] for o in h["outcomes"] if o["outcome_id"] == yes)
        check("1 initial point", len(yes_pts), 1)
        check("initial price 50", yes_pts[0]["price_cents"], 50)

        # Fund + bet
        print("2. Login, deposit, bet")
        r = await api.post("/api/auth/login", json={"pan": BETTOR_PAN, "otp": pyotp.TOTP(TOTP).now()})
        r.raise_for_status()
        hdr = {"Authorization": f"Bearer {r.json()['session_token']}"}
        r = await api.post("/api/wallet/deposit", json={"amount_cents": 5000, "idempotency_key": "p4-dep-0001"}, headers=hdr)
        r.raise_for_status()
        await api.post(f"/api/markets/{mid}/bet", headers=hdr,
                       json={"outcome_id": yes, "stake_cents": 3000, "idempotency_key": "p4-yes-0001"})
        await api.post(f"/api/markets/{mid}/bet", headers=hdr,
                       json={"outcome_id": no, "stake_cents": 1000, "idempotency_key": "p4-no-0001"})

        # History grew and reflects the latest price
        print("3. History after bets")
        h = (await api.get(f"/api/markets/{mid}/history")).json()
        yes_pts = next(o["points"] for o in h["outcomes"] if o["outcome_id"] == yes)
        check("3 points now", len(yes_pts), 3)            # create + 2 bets
        check("latest Yes price 75", yes_pts[-1]["price_cents"], 75)

        # Trades ticker
        print("4. Trades")
        trades = (await api.get(f"/api/markets/{mid}/trades")).json()
        check("2 trades", len(trades), 2)
        check("latest trade is No 1000", (trades[0]["label"], trades[0]["stake_cents"]), ("No", 1000))

        # Portfolio
        print("5. Portfolio")
        pf = (await api.get("/api/portfolio", headers=hdr)).json()
        check("wallet 1000", pf["wallet"]["balance_cents"], 1000)
        mk = next(x for x in pf["markets"] if x["market_id"] == mid)
        stakes = {p["label"]: p["stake_cents"] for p in mk["positions"]}
        check("portfolio Yes stake 3000", stakes.get("Yes"), 3000)

        # SSE stream: read one live event
        print("6. SSE stream")
        got = None
        async with api.stream("GET", f"/api/markets/{mid}/stream") as r:
            async for line in r.aiter_lines():
                if line.startswith("data: "):
                    got = json.loads(line[6:])
                    break
        check("stream Yes price 75", price(got, "Yes"), 75)
        check("stream total pool 4000", got["total_pool_cents"], 4000)

    print()
    print(f"RESULT: {FAIL if _fail else PASS}" + (f" — {_fail} failed" if _fail else " — Phase 4 verified"))
    return 1 if _fail else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
