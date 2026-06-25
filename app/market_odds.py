"""Parimutuel odds: an outcome's price is its share of the total pool, which reads
directly as an implied probability (Kalshi-style cents)."""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app import ledger
from app.models import Market, OddsSnapshot
from app.schemas import MarketOut, OutcomeOut


def _display_bps(outcome, pool: int, total: int, n: int) -> int:
    """Displayed odds in basis points: admin override if set, else pool share (even if no bets)."""
    if outcome.manual_price_bps is not None:
        return outcome.manual_price_bps
    frac = pool / total if total > 0 else 1 / n
    return round(frac * 10000)


async def build_market_out(db: AsyncSession, market: Market) -> MarketOut:
    pools = {o.id: await ledger.balance_cents(db, o.pool_account_id) for o in market.outcomes}
    total = sum(pools.values())
    n = len(market.outcomes) or 1

    outcomes: list[OutcomeOut] = []
    for o in market.outcomes:
        pool = pools[o.id]
        bps = _display_bps(o, pool, total, n)
        outcomes.append(OutcomeOut(
            id=o.id, label=o.label, pool_cents=pool,
            price_cents=round(bps / 100), implied_pct=round(bps / 100, 1),
        ))

    return MarketOut(
        id=market.id, title=market.title, description=market.description,
        status=market.status.value, rake_bps=market.rake_bps, closes_at=market.closes_at,
        resolved_outcome_id=market.resolved_outcome_id, total_pool_cents=total, outcomes=outcomes,
    )


async def record_snapshot(db: AsyncSession, market: Market) -> None:
    """Append a current-odds row per outcome (for the price-history chart). Caller commits."""
    pools = {o.id: await ledger.balance_cents(db, o.pool_account_id) for o in market.outcomes}
    total = sum(pools.values())
    n = len(market.outcomes) or 1
    for o in market.outcomes:
        db.add(OddsSnapshot(market_id=market.id, outcome_id=o.id,
                            price_bps=_display_bps(o, pools[o.id], total, n), pool_cents=pools[o.id]))

