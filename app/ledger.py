"""Double-entry ledger helpers.

Balances are derived from entries (sum of credits minus debits), so the ledger can
never silently drift from its transaction history. EXTERNAL and HOUSE are singleton
system accounts; every user has one USER wallet account.
"""
from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AccountType, LedgerAccount, LedgerEntry, LedgerTx, TxType


async def get_system_account(db: AsyncSession, label: str) -> LedgerAccount:
    """Fetch (creating if needed) a singleton system account: 'EXTERNAL' or 'HOUSE'."""
    acct_type = AccountType[label]
    existing = (
        await db.execute(select(LedgerAccount).where(LedgerAccount.label == label))
    ).scalar_one_or_none()
    if existing:
        return existing
    acct = LedgerAccount(type=acct_type, label=label)
    db.add(acct)
    await db.flush()
    return acct


async def create_user_wallet(db: AsyncSession, user_id: uuid.UUID) -> LedgerAccount:
    acct = LedgerAccount(type=AccountType.USER, user_id=user_id)
    db.add(acct)
    await db.flush()
    return acct


async def post_tx(
    db: AsyncSession,
    tx_type: TxType,
    entries: list[tuple[uuid.UUID, uuid.UUID, int]],
    meta: dict | None = None,
) -> LedgerTx:
    """Atomically record a transaction. `entries` = [(from_account_id, to_account_id, amount_cents)].

    The caller controls the surrounding DB transaction (commit/rollback).
    """
    if not entries:
        raise ValueError("a transaction needs at least one entry")
    tx = LedgerTx(type=tx_type, meta=meta)
    db.add(tx)
    await db.flush()
    for from_id, to_id, amount in entries:
        if amount <= 0:
            raise ValueError("entry amount must be positive")
        if from_id == to_id:
            raise ValueError("entry from and to must differ")
        db.add(LedgerEntry(tx_id=tx.id, from_account_id=from_id, to_account_id=to_id, amount_cents=amount))
    await db.flush()
    return tx


async def balance_cents(db: AsyncSession, account_id: uuid.UUID) -> int:
    credits = (
        await db.execute(
            select(func.coalesce(func.sum(LedgerEntry.amount_cents), 0)).where(
                LedgerEntry.to_account_id == account_id
            )
        )
    ).scalar_one()
    debits = (
        await db.execute(
            select(func.coalesce(func.sum(LedgerEntry.amount_cents), 0)).where(
                LedgerEntry.from_account_id == account_id
            )
        )
    ).scalar_one()
    return int(credits) - int(debits)
