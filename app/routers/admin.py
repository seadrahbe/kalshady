from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app import resolution
from app.cashout import run_cashout
from app.db import get_db
from app.deps import get_bank, require_admin
from app.market_odds import build_market_out, record_snapshot
from app.models import AccountType, CashOut, LedgerAccount, Market, MarketStatus, Outcome
from app.reconcile import reconcile as reconcile_ledger
from app.schemas import (
    CashoutRequest,
    CashoutResult,
    MarketCreate,
    MarketOut,
    OddsUpdate,
    ResolveRequest,
    ResolveResult,
    cents_to_display,
)
from bank import ShadyBankClient

router = APIRouter(prefix="/api/admin", tags=["admin"], dependencies=[Depends(require_admin)])


@router.get("/check")
async def check() -> dict:
    """Validates the admin key (the router-level require_admin dependency does the work)."""
    return {"ok": True}


async def _load_market(db: AsyncSession, market_id: uuid.UUID) -> Market:
    market = (
        await db.execute(
            select(Market).where(Market.id == market_id).options(selectinload(Market.outcomes))
        )
    ).scalar_one_or_none()
    if not market:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "market not found")
    return market


@router.post("/markets", response_model=MarketOut, status_code=status.HTTP_201_CREATED)
async def create_market(body: MarketCreate, db: AsyncSession = Depends(get_db)) -> MarketOut:
    market = Market(
        title=body.title, description=body.description,
        rake_bps=body.rake_bps, closes_at=body.closes_at, status=MarketStatus.OPEN,
    )
    prices = body.outcome_prices
    if prices is not None and len(prices) != len(body.outcomes):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "outcome_prices must match outcomes length")
    db.add(market)
    await db.flush()
    for i, label in enumerate(body.outcomes):
        pool = LedgerAccount(type=AccountType.POOL)
        db.add(pool)
        await db.flush()
        mp = prices[i] * 100 if prices is not None else None
        db.add(Outcome(market_id=market.id, label=label, pool_account_id=pool.id, manual_price_bps=mp))
    await db.commit()
    market = await _load_market(db, market.id)
    await record_snapshot(db, market)   # initial (even-odds) point for the chart
    await db.commit()
    return await build_market_out(db, market)


@router.post("/markets/{market_id}/open", response_model=MarketOut)
async def open_market(market_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> MarketOut:
    market = await _load_market(db, market_id)
    if market.status in (MarketStatus.RESOLVED, MarketStatus.VOID):
        raise HTTPException(status.HTTP_409_CONFLICT, f"market is {market.status.value}")
    market.status = MarketStatus.OPEN
    await db.commit()
    return await build_market_out(db, market)


@router.post("/markets/{market_id}/close", response_model=MarketOut)
async def close_market(market_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> MarketOut:
    market = await _load_market(db, market_id)
    if market.status in (MarketStatus.RESOLVED, MarketStatus.VOID):
        raise HTTPException(status.HTTP_409_CONFLICT, f"market is {market.status.value}")
    market.status = MarketStatus.CLOSED
    await db.commit()
    return await build_market_out(db, market)


@router.post("/markets/{market_id}/odds", response_model=MarketOut)
async def set_odds(market_id: uuid.UUID, body: OddsUpdate, db: AsyncSession = Depends(get_db)) -> MarketOut:
    """Manually set display odds (cents) per outcome. Payouts remain parimutuel on real pools."""
    market = await _load_market(db, market_id)
    by_id = {str(o.id): o for o in market.outcomes}
    for oid, cents in body.prices.items():
        if oid not in by_id:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"unknown outcome {oid}")
        by_id[oid].manual_price_bps = max(0, min(10000, int(cents) * 100))
    await db.commit()
    return await build_market_out(db, await _load_market(db, market_id))


@router.post("/markets/{market_id}/resolve", response_model=ResolveResult)
async def resolve_market(
    market_id: uuid.UUID, body: ResolveRequest, db: AsyncSession = Depends(get_db)
) -> ResolveResult:
    market = await _load_market(db, market_id)
    if market.status not in (MarketStatus.OPEN, MarketStatus.CLOSED):
        raise HTTPException(status.HTTP_409_CONFLICT, f"market is {market.status.value}")
    try:
        summary = await resolution.settle_market(db, market, body.winning_outcome_id)
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))
    await db.commit()
    return ResolveResult(market=await build_market_out(db, await _load_market(db, market_id)), **summary)


@router.post("/markets/{market_id}/void", response_model=ResolveResult)
async def void_market(market_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> ResolveResult:
    market = await _load_market(db, market_id)
    if market.status not in (MarketStatus.OPEN, MarketStatus.CLOSED):
        raise HTTPException(status.HTTP_409_CONFLICT, f"market is {market.status.value}")
    summary = await resolution.void_market(db, market)
    await db.commit()
    return ResolveResult(market=await build_market_out(db, await _load_market(db, market_id)), **summary)


@router.post("/cashout", response_model=CashoutResult)
async def cashout(
    body: CashoutRequest = CashoutRequest(),
    db: AsyncSession = Depends(get_db),
    bank: ShadyBankClient = Depends(get_bank),
) -> CashoutResult:
    """Pay every wallet back to its card. Provide the house OTP (live bank). Safe to re-run:
    settled wallets are skipped (balance 0), and previously-FAILED transfers are retried."""
    summary = await run_cashout(db, bank, otp=body.otp)
    return CashoutResult(sent_display=cents_to_display(summary["sent_cents"]), **summary)


@router.get("/cashouts")
async def list_cashouts(db: AsyncSession = Depends(get_db)) -> list[dict]:
    rows = (await db.execute(select(CashOut).order_by(CashOut.created_at.desc()))).scalars().all()
    return [{"id": str(c.id), "user_id": str(c.user_id), "amount_cents": c.amount_cents,
             "status": c.status.value, "error": c.error} for c in rows]


@router.get("/reconcile")
async def reconcile(
    otp: str | None = None,
    db: AsyncSession = Depends(get_db),
    bank: ShadyBankClient = Depends(get_bank),
) -> dict:
    """Cross-check our ledger against the bank (by sp:* tags) and verify internal solvency.
    Pass ?otp= for the live house account."""
    return await reconcile_ledger(db, bank, otp=otp)
