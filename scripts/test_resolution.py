#!/usr/bin/env python3
"""Phase 3 acceptance test: resolution, parimutuel payout, and end-of-event cash-out.

Two bettors bet on a Yes/No market (5% rake); Yes wins; payouts split by stake; then the
end-of-event cash-out pushes every wallet back to its card at the bank.

Prereqs: bank up + FRESH seed (both bettors at 100, house at 0), our API up (:8010), app DB reset.
    ./.venv/bin/python scripts/test_resolution.py
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
ADMIN = {"X-Admin-Key": "dev-admin-key"}
BANK = "http://127.0.0.1:8021"
TOTP = "JBSWY3DPEHPK3PXP"
B1_PAN, B2_PAN, HOUSE_PAN = "8997000000000001", "8997000000000003", "8997000000000002"

PASS, FAIL = "\033[32mPASS\033[0m", "\033[31mFAIL\033[0m"
_fail = 0


def check(label, got, want):
    global _fail
    ok = got == want
    _fail += 0 if ok else 1
    print(f"  [{PASS if ok else FAIL}] {label}: got {got!r}, want {want!r}")


async def bank_bal(bank, pan) -> Decimal:
    return Decimal(str((await bank.balance(await bank.login(pan=pan, pin="1111" if pan != HOUSE_PAN else "4242")))["balance"]))


async def login_deposit(api, pan, cents) -> dict:
    r = await api.post("/api/auth/login", json={"pan": pan, "otp": pyotp.TOTP(TOTP).now()})
    r.raise_for_status()
    hdr = {"Authorization": f"Bearer {r.json()['session_token']}"}
    r = await api.post("/api/wallet/deposit", json={"amount_cents": cents, "idempotency_key": f"dep-{pan}"}, headers=hdr)
    r.raise_for_status()
    return hdr


async def wallet(api, hdr) -> int:
    return (await api.get("/api/wallet", headers=hdr)).json()["balance_cents"]


async def bet(api, hdr, mid, oid, cents, key) -> dict:
    r = await api.post(f"/api/markets/{mid}/bet", headers=hdr,
                       json={"outcome_id": oid, "stake_cents": cents, "idempotency_key": key})
    r.raise_for_status()
    return r.json()


async def main() -> int:
    async with ShadyBankClient(BANK) as bank, httpx.AsyncClient(base_url=API, timeout=20) as api:
        # Market: Yes/No, 5% rake
        r = await api.post("/api/admin/markets", headers=ADMIN,
                           json={"title": "Will the talk start on time?", "outcomes": ["Yes", "No"], "rake_bps": 500})
        r.raise_for_status()
        m = r.json()
        mid = m["id"]
        yes = next(o["id"] for o in m["outcomes"] if o["label"] == "Yes")
        no = next(o["id"] for o in m["outcomes"] if o["label"] == "No")

        print("1. Two bettors fund + bet")
        h1 = await login_deposit(api, B1_PAN, 5000)
        h2 = await login_deposit(api, B2_PAN, 5000)
        # bettor1: Yes 30 ; bettor2: Yes 10, No 20
        await bet(api, h1, mid, yes, 3000, "rt-b1-yes")
        await bet(api, h2, mid, yes, 1000, "rt-b2-yes")
        m = (await bet(api, h2, mid, no, 2000, "rt-b2-no"))["market"]
        check("total pool 6000", m["total_pool_cents"], 6000)
        check("Yes price 67", next(o["price_cents"] for o in m["outcomes"] if o["label"] == "Yes"), 67)  # 4000/6000

        print("2. Resolve: Yes wins (5% rake)")
        r = await api.post(f"/api/admin/markets/{mid}/resolve", headers=ADMIN, json={"winning_outcome_id": yes})
        r.raise_for_status()
        res = r.json()
        check("rake 300", res["rake_cents"], 300)
        check("paid 5700", res["paid_cents"], 5700)
        check("payout_count 2", res["payout_count"], 2)
        check("status RESOLVED", res["market"]["status"], "RESOLVED")
        check("pools drained", res["market"]["total_pool_cents"], 0)

        # wallets: b1 2000+4275=6275 ; b2 2000+1425=3425
        check("bettor1 wallet 6275", await wallet(api, h1), 6275)
        check("bettor2 wallet 3425", await wallet(api, h2), 3425)

        print("3. End-of-event cash-out")
        b1_before = await bank_bal(bank, B1_PAN)
        b2_before = await bank_bal(bank, B2_PAN)
        house_before = await bank_bal(bank, HOUSE_PAN)
        print(f"   bank before cashout: b1={b1_before} b2={b2_before} house={house_before}")
        r = await api.post("/api/admin/cashout", headers=ADMIN)
        r.raise_for_status()
        co = r.json()
        check("sent_count 2", co["sent_count"], 2)
        check("sent_cents 9700", co["sent_cents"], 9700)

        check("bettor1 wallet 0 after", await wallet(api, h1), 0)
        check("bettor2 wallet 0 after", await wallet(api, h2), 0)
        check("bettor1 bank +62.75", await bank_bal(bank, B1_PAN), b1_before + Decimal("62.75"))
        check("bettor2 bank +34.25", await bank_bal(bank, B2_PAN), b2_before + Decimal("34.25"))
        check("house bank -97 (keeps 3 rake)", await bank_bal(bank, HOUSE_PAN), house_before - Decimal("97.00"))

    print()
    print(f"RESULT: {FAIL if _fail else PASS}" + (f" — {_fail} failed" if _fail else " — Phase 3 verified"))
    return 1 if _fail else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
