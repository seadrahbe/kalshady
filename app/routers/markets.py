from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app import ledger
from app.config import get_settings
from app.db import get_db, get_sessionmaker
from app.deps import get_current_user
from app.market_odds import build_market_out, record_snapshot
from app.models import Bet, LedgerAccount, Market, MarketStatus, OddsSnapshot, Outcome, TxType, User
from app.schemas import (
    BetRequest,
    BetResponse,
    HistoryPoint,
    MarketHistory,
    MarketOut,
    OutcomeHistory,
    PositionItem,
    PositionOut,
    TradeItem,
    WalletOut,
    cents_to_display,
)

router = APIRouter(prefix="/api/markets", tags=["markets"])


async def _load_market(db: AsyncSession, market_id: uuid.UUID) -> Market:
    market = (
        await db.execute(
            select(Market).where(Market.id == market_id).options(selectinload(Market.outcomes))
        )
    ).scalar_one_or_none()
    if not market:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "market not found")
    return market


async def _wallet_out(db: AsyncSession, user: User) -> WalletOut:
    bal = await ledger.balance_cents(db, user.ledger_account_id)
    return WalletOut(balance_cents=bal, balance_display=cents_to_display(bal))


@router.get("", response_model=list[MarketOut])
async def list_markets(db: AsyncSession = Depends(get_db)) -> list[MarketOut]:
    markets = (
        await db.execute(select(Market).options(selectinload(Market.outcomes)).order_by(Market.created_at.desc()))
    ).scalars().all()
    return [await build_market_out(db, m) for m in markets]


@router.get("/{market_id}", response_model=MarketOut)
async def get_market(market_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> MarketOut:
    return await build_market_out(db, await _load_market(db, market_id))


@router.post("/{market_id}/bet", response_model=BetResponse)
async def place_bet(
    market_id: uuid.UUID,
    body: BetRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> BetResponse:
    min_bet = get_settings().min_bet_cents
    if body.stake_cents < min_bet:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"minimum bet is {min_bet} cents")

    # Idempotency fast-path.
    existing = (
        await db.execute(select(Bet).where(Bet.idempotency_key == body.idempotency_key))
    ).scalar_one_or_none()
    if existing is not None:
        market = await _load_market(db, existing.market_id)
        return BetResponse(bet_id=existing.id, wallet=await _wallet_out(db, user),
                           market=await build_market_out(db, market))

    market = await _load_market(db, market_id)
    if market.status != MarketStatus.OPEN:
        raise HTTPException(status.HTTP_409_CONFLICT, f"market is {market.status.value}")
    if market.closes_at and datetime.now(timezone.utc) >= market.closes_at:
        raise HTTPException(status.HTTP_409_CONFLICT, "betting has closed")
    outcome = next((o for o in market.outcomes if o.id == body.outcome_id), None)
    if outcome is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "outcome not in this market")

    # Lock the bettor's wallet row to serialize concurrent bets (prevents overspend).
    await db.execute(
        select(LedgerAccount).where(LedgerAccount.id == user.ledger_account_id).with_for_update()
    )
    bal = await ledger.balance_cents(db, user.ledger_account_id)
    if bal < body.stake_cents:
        raise HTTPException(status.HTTP_402_PAYMENT_REQUIRED, "insufficient wallet balance")

    tx = await ledger.post_tx(
        db, TxType.BET,
        entries=[(user.ledger_account_id, outcome.pool_account_id, body.stake_cents)],
        meta={"market_id": str(market.id), "outcome_id": str(outcome.id)},
    )
    bet = Bet(
        market_id=market.id, outcome_id=outcome.id, user_id=user.id,
        stake_cents=body.stake_cents, idempotency_key=body.idempotency_key, tx_id=tx.id,
    )
    db.add(bet)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        existing = (
            await db.execute(select(Bet).where(Bet.idempotency_key == body.idempotency_key))
        ).scalar_one()
        market = await _load_market(db, existing.market_id)
        return BetResponse(bet_id=existing.id, wallet=await _wallet_out(db, user),
                           market=await build_market_out(db, market))
    await db.commit()

    market = await _load_market(db, market_id)  # reload for fresh pools/odds
    await record_snapshot(db, market)           # capture odds for the price-history chart
    await db.commit()
    return BetResponse(bet_id=bet.id, wallet=await _wallet_out(db, user),
                       market=await build_market_out(db, market))


async def compute_positions(db: AsyncSession, market: Market, user_id: uuid.UUID) -> list[PositionItem]:
    """A user's stake + projected parimutuel payout-if-win per outcome in one market."""
    pools = {o.id: await ledger.balance_cents(db, o.pool_account_id) for o in market.outcomes}
    total = sum(pools.values())
    net_total = total * (10000 - market.rake_bps) / 10000

    bets = (await db.execute(
        select(Bet).where(Bet.market_id == market.id, Bet.user_id == user_id)
    )).scalars().all()
    stake_by_outcome: dict[uuid.UUID, int] = {}
    for b in bets:
        stake_by_outcome[b.outcome_id] = stake_by_outcome.get(b.outcome_id, 0) + b.stake_cents

    items: list[PositionItem] = []
    for o in market.outcomes:
        stake = stake_by_outcome.get(o.id, 0)
        if stake == 0:
            continue
        pool = pools[o.id]
        projected = int(stake / pool * net_total) if pool > 0 else 0
        items.append(PositionItem(outcome_id=o.id, label=o.label, stake_cents=stake,
                                  projected_payout_cents=projected))
    return items


@router.get("/{market_id}/position", response_model=PositionOut)
async def my_position(
    market_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PositionOut:
    market = await _load_market(db, market_id)
    return PositionOut(market_id=market_id, positions=await compute_positions(db, market, user.id))


@router.get("/{market_id}/history", response_model=MarketHistory)
async def market_history(market_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> MarketHistory:
    """Odds over time per outcome (feeds the Kalshi-style price chart)."""
    market = await _load_market(db, market_id)
    rows = (await db.execute(
        select(OddsSnapshot).where(OddsSnapshot.market_id == market_id).order_by(OddsSnapshot.ts)
    )).scalars().all()
    pts: dict[uuid.UUID, list[HistoryPoint]] = {}
    for s in rows:
        pts.setdefault(s.outcome_id, []).append(
            HistoryPoint(ts=s.ts, price_cents=round(s.price_bps / 100), pool_cents=s.pool_cents)
        )
    return MarketHistory(
        market_id=market_id,
        outcomes=[OutcomeHistory(outcome_id=o.id, label=o.label, points=pts.get(o.id, []))
                  for o in market.outcomes],
    )


@router.get("/{market_id}/trades", response_model=list[TradeItem])
async def recent_trades(
    market_id: uuid.UUID, limit: int = 50, db: AsyncSession = Depends(get_db)
) -> list[TradeItem]:
    """Recent bets (anonymized) for a live trades ticker."""
    market = await _load_market(db, market_id)
    label_by = {o.id: o.label for o in market.outcomes}
    rows = (await db.execute(
        select(Bet).where(Bet.market_id == market_id).order_by(Bet.created_at.desc()).limit(min(limit, 200))
    )).scalars().all()
    return [TradeItem(ts=b.created_at, outcome_id=b.outcome_id,
                      label=label_by.get(b.outcome_id, ""), stake_cents=b.stake_cents) for b in rows]


@router.get("/{market_id}/stream")
async def stream_odds(market_id: uuid.UUID) -> StreamingResponse:
    """Server-Sent Events: pushes current market odds every ~2s (live updates without polling)."""
    async def gen():
        while True:
            async with get_sessionmaker()() as s:
                market = (await s.execute(
                    select(Market).where(Market.id == market_id).options(selectinload(Market.outcomes))
                )).scalar_one_or_none()
                if market is None:
                    yield "event: error\ndata: market not found\n\n"
                    return
                out = await build_market_out(s, market)
            yield f"data: {out.model_dump_json()}\n\n"
            await asyncio.sleep(2)

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
