from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


def cents_to_display(cents: int) -> str:
    sign = "-" if cents < 0 else ""
    c = abs(cents)
    return f"{sign}{c // 100}.{c % 100:02d}"


class LoginRequest(BaseModel):
    pan: str = Field(..., description="ShadyBucks card number")
    otp: str = Field(..., description="One-time passcode from the bettor's authenticator")


class UserOut(BaseModel):
    id: uuid.UUID
    name: str
    shadybank_account_id: int


class WalletOut(BaseModel):
    balance_cents: int
    balance_display: str


class MeResponse(BaseModel):
    user: UserOut
    wallet: WalletOut


class LoginResponse(MeResponse):
    session_token: str = Field(..., description="Bearer token for subsequent requests (also set as a cookie)")


class DepositRequest(BaseModel):
    amount_cents: int = Field(..., gt=0, description="Amount to move from the bettor's bank account into their wallet")
    idempotency_key: str = Field(..., min_length=8, max_length=80,
                                 description="Client-generated key so retries don't double-charge")


class DepositResponse(BaseModel):
    deposit_id: uuid.UUID
    status: str
    wallet: WalletOut


# ---- markets ----------------------------------------------------------------
class OutcomeOut(BaseModel):
    id: uuid.UUID
    label: str
    pool_cents: int
    price_cents: int      # 0-100, parimutuel implied price (== implied probability)
    implied_pct: float    # price as a percentage, 1 decimal


class MarketOut(BaseModel):
    id: uuid.UUID
    title: str
    description: str | None
    status: str
    rake_bps: int
    closes_at: datetime | None = None
    resolved_outcome_id: uuid.UUID | None = None
    total_pool_cents: int
    outcomes: list[OutcomeOut]


class MarketCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=280)
    description: str | None = Field(None, max_length=2000)
    rake_bps: int = Field(3000, ge=0, le=10000, description="House cut in basis points (default 30%)")
    closes_at: datetime | None = None
    outcomes: list[str] = Field(..., min_length=2, description="Outcome labels, e.g. ['Yes','No']")
    outcome_prices: list[int] | None = Field(
        None, description="Optional admin-set display odds in cents (0-100), parallel to outcomes")


class OddsUpdate(BaseModel):
    prices: dict[str, int] = Field(..., description="Map of outcome_id -> display odds in cents (0-100)")


class BetRequest(BaseModel):
    outcome_id: uuid.UUID
    stake_cents: int = Field(..., gt=0)
    idempotency_key: str = Field(..., min_length=8, max_length=80)


class BetResponse(BaseModel):
    bet_id: uuid.UUID
    wallet: WalletOut
    market: MarketOut


class PositionItem(BaseModel):
    outcome_id: uuid.UUID
    label: str
    stake_cents: int
    projected_payout_cents: int   # if this outcome wins (parimutuel, net of rake)


class PositionOut(BaseModel):
    market_id: uuid.UUID
    positions: list[PositionItem]


# ---- resolution / cash-out -------------------------------------------------
class ResolveRequest(BaseModel):
    winning_outcome_id: uuid.UUID


class ResolveResult(BaseModel):
    market: MarketOut
    refunded: bool
    total_cents: int
    rake_cents: int
    paid_cents: int
    payout_count: int


# ---- live-odds data (Phase 4) ----------------------------------------------
class HistoryPoint(BaseModel):
    ts: datetime
    price_cents: int
    pool_cents: int


class OutcomeHistory(BaseModel):
    outcome_id: uuid.UUID
    label: str
    points: list[HistoryPoint]


class MarketHistory(BaseModel):
    market_id: uuid.UUID
    outcomes: list[OutcomeHistory]


class TradeItem(BaseModel):
    ts: datetime
    outcome_id: uuid.UUID
    label: str
    stake_cents: int


class PortfolioMarket(BaseModel):
    market_id: uuid.UUID
    title: str
    status: str
    positions: list[PositionItem]


class PortfolioOut(BaseModel):
    wallet: WalletOut
    markets: list[PortfolioMarket]


class CashoutRequest(BaseModel):
    otp: str | None = Field(None, description="House account OTP (live bank); omit for dev/PIN fallback")


class CashoutResult(BaseModel):
    sent_count: int
    failed_count: int
    sent_cents: int
    sent_display: str
    failures: list[dict]

