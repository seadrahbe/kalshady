from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    String,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def _uuid() -> uuid.UUID:
    return uuid.uuid4()


class AccountType(str, enum.Enum):
    EXTERNAL = "EXTERNAL"   # the outside world / the bank (money source & sink)
    HOUSE = "HOUSE"         # ShadyPredict's own take (rake, etc.)
    USER = "USER"           # a bettor's internal wallet
    POOL = "POOL"           # a market-outcome stake pool (Phase 2)


class TxType(str, enum.Enum):
    DEPOSIT = "DEPOSIT"
    BET = "BET"
    PAYOUT = "PAYOUT"
    REFUND = "REFUND"
    CASHOUT = "CASHOUT"
    RAKE = "RAKE"
    ADJUST = "ADJUST"


class DepositStatus(str, enum.Enum):
    PENDING = "PENDING"      # row created, bank transfer not yet confirmed
    CONFIRMED = "CONFIRMED"  # bank moved the money and wallet credited
    FAILED = "FAILED"        # bank rejected; no wallet change


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    shadybank_account_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    pan_enc: Mapped[str] = mapped_column(String(512))  # encrypted card number
    ledger_account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("ledger_accounts.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    wallet: Mapped["LedgerAccount"] = relationship(foreign_keys=[ledger_account_id])


class LedgerAccount(Base):
    __tablename__ = "ledger_accounts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    type: Mapped[AccountType] = mapped_column(Enum(AccountType, name="account_type"), index=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    label: Mapped[str | None] = mapped_column(String(80), nullable=True)  # 'EXTERNAL'/'HOUSE' singletons
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class LedgerTx(Base):
    __tablename__ = "ledger_tx"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    type: Mapped[TxType] = mapped_column(Enum(TxType, name="tx_type"), index=True)
    meta: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    entries: Mapped[list["LedgerEntry"]] = relationship(back_populates="tx", cascade="all, delete-orphan")


class LedgerEntry(Base):
    """Double-entry: moves `amount_cents` from one ledger account to another."""

    __tablename__ = "ledger_entries"
    __table_args__ = (CheckConstraint("amount_cents > 0", name="amount_positive"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    tx_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("ledger_tx.id"), index=True)
    from_account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("ledger_accounts.id"), index=True)
    to_account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("ledger_accounts.id"), index=True)
    amount_cents: Mapped[int] = mapped_column(BigInteger)

    tx: Mapped["LedgerTx"] = relationship(back_populates="entries")


class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)  # opaque token (also the cookie value)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    bank_token_enc: Mapped[str] = mapped_column(String(1024))      # encrypted shadybank bearer token
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)


class OddsSnapshot(Base):
    """Point-in-time odds for an outcome, written on each bet — feeds the price chart."""

    __tablename__ = "odds_snapshots"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    market_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("markets.id"), index=True)
    outcome_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("outcomes.id"), index=True)
    price_bps: Mapped[int] = mapped_column(BigInteger)   # 0-10000 (implied probability x100)
    pool_cents: Mapped[int] = mapped_column(BigInteger)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)


class CashoutStatus(str, enum.Enum):
    PENDING = "PENDING"
    SENT = "SENT"
    FAILED = "FAILED"


class CashOut(Base):
    __tablename__ = "cashouts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    amount_cents: Mapped[int] = mapped_column(BigInteger)
    status: Mapped[CashoutStatus] = mapped_column(
        Enum(CashoutStatus, name="cashout_status"), default=CashoutStatus.PENDING, index=True
    )
    tx_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("ledger_tx.id"), nullable=True)
    error: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class MarketStatus(str, enum.Enum):
    OPEN = "OPEN"          # accepting bets
    CLOSED = "CLOSED"      # betting closed, awaiting resolution
    RESOLVED = "RESOLVED"  # winner decided, payouts done
    VOID = "VOID"          # cancelled, stakes refunded


class Market(Base):
    __tablename__ = "markets"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    title: Mapped[str] = mapped_column(String(280))
    description: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    status: Mapped[MarketStatus] = mapped_column(
        Enum(MarketStatus, name="market_status"), default=MarketStatus.OPEN, index=True
    )
    rake_bps: Mapped[int] = mapped_column(BigInteger, default=0)  # house cut in basis points (0-10000)
    closes_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_outcome_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    outcomes: Mapped[list["Outcome"]] = relationship(back_populates="market", cascade="all, delete-orphan")


class Outcome(Base):
    __tablename__ = "outcomes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    market_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("markets.id"), index=True)
    label: Mapped[str] = mapped_column(String(280))
    pool_account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("ledger_accounts.id"))
    # Admin-set display odds (basis points). When set, overrides the pool-derived price shown
    # to users; payouts are still parimutuel on the real pools.
    manual_price_bps: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    market: Mapped["Market"] = relationship(back_populates="outcomes")


class Bet(Base):
    __tablename__ = "bets"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    market_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("markets.id"), index=True)
    outcome_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("outcomes.id"), index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    stake_cents: Mapped[int] = mapped_column(BigInteger)
    idempotency_key: Mapped[str] = mapped_column(String(80), unique=True)
    tx_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("ledger_tx.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Deposit(Base):
    __tablename__ = "deposits"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    amount_cents: Mapped[int] = mapped_column(BigInteger)
    idempotency_key: Mapped[str] = mapped_column(String(80), unique=True)
    status: Mapped[DepositStatus] = mapped_column(
        Enum(DepositStatus, name="deposit_status"), default=DepositStatus.PENDING, index=True
    )
    bank_description: Mapped[str] = mapped_column(String(120))  # tag echoed to the bank for reconciliation
    tx_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("ledger_tx.id"), nullable=True)
    error: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
