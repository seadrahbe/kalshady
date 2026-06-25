from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import ledger, models  # noqa: F401  (models import registers tables on Base.metadata)
from app.config import get_settings
from app.db import Base, get_engine, get_sessionmaker
from app.routers import admin, auth, markets, portfolio, wallet
from bank import ShadyBankClient


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()

    # Dev convenience: auto-create tables. In prod set SP_AUTO_CREATE_TABLES=false and use Alembic.
    if settings.auto_create_tables:
        async with get_engine().begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    # Ensure singleton system ledger accounts exist.
    async with get_sessionmaker()() as db:
        await ledger.get_system_account(db, "EXTERNAL")
        await ledger.get_system_account(db, "HOUSE")
        await db.commit()

    app.state.bank = ShadyBankClient(settings.bank_api_url)
    try:
        yield
    finally:
        await app.state.bank.aclose()
        await get_engine().dispose()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="ShadyPredict API", version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,   # we use bearer tokens (not cookies) cross-origin, so "*" is allowed
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health", tags=["meta"])
    async def health() -> dict:
        return {"status": "ok"}

    app.include_router(auth.router)
    app.include_router(wallet.router)
    app.include_router(markets.router)
    app.include_router(portfolio.router)
    app.include_router(admin.router)
    return app


app = create_app()
