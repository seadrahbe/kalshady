"""Market settlement: parimutuel payout, rake, and refunds.

Money model: stakes live in per-outcome POOL ledger accounts. On settlement we drain
every pool into HOUSE and pay winners out of HOUSE in a single atomic transaction; HOUSE
is left holding exactly the rake. Refund (void) returns each stake from its pool to the
bettor. Balances are integer cents; the net pool is split by largest-remainder so payouts
sum exactly.
"""
from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import ledger
from app.models import Bet, Market, MarketStatus, TxType, User


def distribute(net_cents: int, stakes: dict[uuid.UUID, int], pool_cents: int) -> dict[uuid.UUID, int]:
    """Split `net_cents` among stakers in proportion to stake/pool, summing exactly to net.

    Leftover cents go to the largest fractional remainders (deterministic, by uid as tiebreak).
    """
    if pool_cents <= 0 or net_cents <= 0:
        return {}
    floors = {uid: (net_cents * stake) // pool_cents for uid, stake in stakes.items()}
    remainder = net_cents - sum(floors.values())
    # rank by fractional part (descending), uid as a stable tiebreak
    ranked = sorted(stakes, key=lambda u: ((net_cents * stakes[u]) % pool_cents, str(u)), reverse=True)
    for i in range(remainder):
        floors[ranked[i]] += 1
    return floors


async def _wallet_map(db: AsyncSession, user_ids: list[uuid.UUID]) -> dict[uuid.UUID, uuid.UUID]:
    if not user_ids:
        return {}
    rows = (await db.execute(
        select(User.id, User.ledger_account_id).where(User.id.in_(user_ids))
    )).all()
    return {uid: la for uid, la in rows}


async def settle_market(db: AsyncSession, market: Market, winning_outcome_id: uuid.UUID) -> dict:
    """Resolve to a winning outcome and pay out. Caller commits."""
    if winning_outcome_id not in {o.id for o in market.outcomes}:
        raise ValueError("winning outcome not in this market")

    pools = {o.id: await ledger.balance_cents(db, o.pool_account_id) for o in market.outcomes}
    total = sum(pools.values())
    win_pool = pools[winning_outcome_id]

    # No winning-side money -> nobody can win; refund everyone.
    if total > 0 and win_pool == 0:
        result = await void_market(db, market)
        result["refunded"] = True
        return result

    house = await ledger.get_system_account(db, "HOUSE")
    rake = total * market.rake_bps // 10000
    net = total - rake

    winner_rows = (await db.execute(
        select(Bet.user_id, func.sum(Bet.stake_cents))
        .where(Bet.market_id == market.id, Bet.outcome_id == winning_outcome_id)
        .group_by(Bet.user_id)
    )).all()
    winner_stakes = {uid: int(s) for uid, s in winner_rows}
    payouts = distribute(net, winner_stakes, win_pool)
    wallets = await _wallet_map(db, list(payouts))

    entries: list[tuple[uuid.UUID, uuid.UUID, int]] = []
    for o in market.outcomes:                      # drain every pool into HOUSE
        if pools[o.id] > 0:
            entries.append((o.pool_account_id, house.id, pools[o.id]))
    for uid, amt in payouts.items():               # HOUSE pays winners; keeps the rake
        if amt > 0:
            entries.append((house.id, wallets[uid], amt))

    if entries:
        await ledger.post_tx(db, TxType.PAYOUT, entries,
                             meta={"market_id": str(market.id), "winning_outcome_id": str(winning_outcome_id)})

    market.status = MarketStatus.RESOLVED
    market.resolved_outcome_id = winning_outcome_id
    return {"refunded": False, "total_cents": total, "rake_cents": rake,
            "paid_cents": sum(payouts.values()), "payout_count": len([a for a in payouts.values() if a > 0])}


async def void_market(db: AsyncSession, market: Market) -> dict:
    """Refund every stake to its bettor and mark the market VOID. Caller commits."""
    pool_of = {o.id: o.pool_account_id for o in market.outcomes}
    bets = (await db.execute(select(Bet).where(Bet.market_id == market.id))).scalars().all()
    wallets = await _wallet_map(db, list({b.user_id for b in bets}))

    entries = [(pool_of[b.outcome_id], wallets[b.user_id], b.stake_cents) for b in bets if b.stake_cents > 0]
    if entries:
        await ledger.post_tx(db, TxType.REFUND, entries, meta={"market_id": str(market.id)})

    market.status = MarketStatus.VOID
    return {"refunded": True, "total_cents": sum(b.stake_cents for b in bets),
            "rake_cents": 0, "paid_cents": sum(b.stake_cents for b in bets),
            "payout_count": len(entries)}
