"""Reconciliation: prove our ledger agrees with the bank and with itself.

Three checks:
  1. Tag match  — every CONFIRMED deposit / SENT cash-out has a matching bank transaction
                  (by the `sp:deposit:<id>` / `sp:cashout:<id>` description tag) of the right amount.
  2. Money sum  — net bucks in our system (USER+POOL+HOUSE wallets) == total deposited - total cashed.
  3. Solvency   — no USER or POOL ledger account is negative (would mean an overspend bug).
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import ledger
from app.house import house_login
from app.models import (
    AccountType,
    CashOut,
    CashoutStatus,
    Deposit,
    DepositStatus,
    LedgerAccount,
)
from bank import ShadyBankClient


async def reconcile(db: AsyncSession, bank: ShadyBankClient, otp: str | None = None) -> dict:
    house_token = await house_login(bank, otp)
    bank_txns = await bank.transactions(house_token)
    bank_by_tag = {
        (t.get("description") or ""): t
        for t in bank_txns
        if (t.get("description") or "").startswith("sp:")
    }

    deposits = (await db.execute(
        select(Deposit).where(Deposit.status == DepositStatus.CONFIRMED)
    )).scalars().all()
    cashouts = (await db.execute(
        select(CashOut).where(CashOut.status == CashoutStatus.SENT)
    )).scalars().all()

    expected = {f"sp:deposit:{d.id}": d.amount_cents for d in deposits}
    expected.update({f"sp:cashout:{c.id}": c.amount_cents for c in cashouts})

    missing_at_bank, amount_mismatch = [], []
    for tag, cents in expected.items():
        bt = bank_by_tag.get(tag)
        if bt is None:
            missing_at_bank.append(tag)
        elif round(float(bt["amount"]) * 100) != cents:
            amount_mismatch.append({"tag": tag, "ours_cents": cents,
                                    "bank_cents": round(float(bt["amount"]) * 100)})
    unknown_at_bank = [tag for tag in bank_by_tag if tag not in expected]

    # Money sum + solvency over our ledger accounts.
    accounts = (await db.execute(select(LedgerAccount))).scalars().all()
    net_in_system = 0
    negative_wallets = []
    for a in accounts:
        bal = await ledger.balance_cents(db, a.id)
        if a.type in (AccountType.USER, AccountType.HOUSE, AccountType.POOL):
            net_in_system += bal
        if a.type in (AccountType.USER, AccountType.POOL) and bal < 0:
            negative_wallets.append({"account_id": str(a.id), "type": a.type.value, "balance_cents": bal})

    total_deposited = sum(d.amount_cents for d in deposits)
    total_cashed = sum(c.amount_cents for c in cashouts)
    money_balanced = net_in_system == (total_deposited - total_cashed)

    ok = not (missing_at_bank or unknown_at_bank or amount_mismatch or negative_wallets) and money_balanced
    return {
        "ok": ok,
        "confirmed_deposits": len(deposits),
        "sent_cashouts": len(cashouts),
        "bank_sp_txns": len(bank_by_tag),
        "total_deposited_cents": total_deposited,
        "total_cashed_cents": total_cashed,
        "net_in_system_cents": net_in_system,
        "money_balanced": money_balanced,
        "missing_at_bank": missing_at_bank,
        "unknown_at_bank": unknown_at_bank,
        "amount_mismatch": amount_mismatch,
        "negative_wallets": negative_wallets,
    }
