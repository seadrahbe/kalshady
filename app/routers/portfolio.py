from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app import ledger
from app.db import get_db
from app.deps import get_current_user
from app.models import Bet, Market, User
from app.routers.markets import compute_positions
from app.schemas import PortfolioMarket, PortfolioOut, WalletOut, cents_to_display

router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])


@router.get("", response_model=PortfolioOut)
async def portfolio(
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> PortfolioOut:
    """The bettor's wallet plus their positions across every market they've bet in."""
    bal = await ledger.balance_cents(db, user.ledger_account_id)
    wallet = WalletOut(balance_cents=bal, balance_display=cents_to_display(bal))

    market_ids = (await db.execute(
        select(Bet.market_id).where(Bet.user_id == user.id).distinct()
    )).scalars().all()

    markets: list[PortfolioMarket] = []
    for mid in market_ids:
        market = (await db.execute(
            select(Market).where(Market.id == mid).options(selectinload(Market.outcomes))
        )).scalar_one()
        positions = await compute_positions(db, market, user.id)
        markets.append(PortfolioMarket(market_id=market.id, title=market.title,
                                       status=market.status.value, positions=positions))
    return PortfolioOut(wallet=wallet, markets=markets)
