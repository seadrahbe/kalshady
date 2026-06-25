# ShadyPredict — Dev setup

Backend-only. Two stacks run side by side: the **self-hosted shadybank** (money rail) and
**our FastAPI backend** + its own Postgres.

## Prereqs
- Docker (daemon running), Python 3.13, the repo's `.venv` (`/opt/homebrew/bin/python3.13 -m venv .venv`).
- `./.venv/bin/pip install -r requirements.txt`

## Ports
| Service | Port | Notes |
|---|---|---|
| shadybank API | 8021 | self-hosted, amd64-emulated (Apple Silicon) |
| our Postgres (`shadypredict-db`) | 5433 | dedicated container |
| our API | 8010 | FastAPI / uvicorn |

## 1. Bring up shadybank (money rail)
```bash
cd vendor-shadybank
docker compose up -d db redis api-endpoint     # frontend not needed (and won't build on arm64)
```
Wait until `curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8021/api/balance` returns `401`.

Seed test fixtures (funded "Test Bettor" + "ShadyPredict House"):
```bash
docker compose -f vendor-shadybank/docker-compose.yml exec -T db \
  psql -U shadybucks -d shadybucks < seed.sql
```
Test cards: bettor `8997000000000001` (OTP secret `JBSWY3DPEHPK3PXP`, PIN `1111`, starts 100),
house `8997000000000002` (PIN `4242`).

## 2. Our Postgres
```bash
docker run -d --name shadypredict-db \
  -e POSTGRES_USER=shadypredict -e POSTGRES_PASSWORD=shadypredict -e POSTGRES_DB=shadypredict \
  -p 5433:5432 postgres:16
```

## 3. Our API
```bash
./.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8010
```
- OpenAPI spec: http://127.0.0.1:8010/openapi.json   ·   Docs: http://127.0.0.1:8010/docs
- Config via `.env` (`SP_*`); `SP_FERNET_KEY` encrypts bank tokens at rest.

## Tests
```bash
./.venv/bin/python scripts/test_roundtrip.py     # Phase 0: bank deposit->cash-out
./.venv/bin/python scripts/demo_push_transfer.py # P2P credit demonstration
./.venv/bin/python scripts/test_backend.py       # Phase 1: login + PUSH deposit + idempotency
./.venv/bin/python scripts/test_markets.py       # Phase 2: markets + parimutuel betting + odds
./.venv/bin/python scripts/test_resolution.py    # Phase 3: resolve + payout + cash-out (needs 2 seeded bettors)
./.venv/bin/python scripts/test_phase4.py        # Phase 4: history + trades + portfolio + SSE
./.venv/bin/python scripts/test_phase5.py        # Phase 5: min-bet, throttle, concurrency safety, reconcile
./.venv/bin/python scripts/live_smoke.py         # live bank read-only check (uses .env.live)
```

## Migrations (Alembic)
Dev auto-creates tables (`SP_AUTO_CREATE_TABLES=true`). For prod, set it false and use Alembic:
```bash
./.venv/bin/alembic upgrade head            # apply migrations
./.venv/bin/alembic revision --autogenerate -m "describe change"   # after model changes
```
Note: if you DROP/recreate the schema under a running server, restart uvicorn (asyncpg caches plans).

Reset notes: `scripts/test_resolution.py` needs both bettors funded at the bank. Before a clean
run: reset the app DB (below) and top up bank balances:
```bash
docker compose -f vendor-shadybank/docker-compose.yml exec -T db psql -U shadybucks -d shadybucks -c \
 "UPDATE accounts SET balance=100,available=100 WHERE id IN (SELECT account_id FROM cards WHERE pan IN ('8997000000000001','8997000000000003'));
  UPDATE accounts SET balance=0,available=0 WHERE id IN (SELECT account_id FROM cards WHERE pan='8997000000000002');"
```

## Reset state
```bash
# bank: fresh schema + reseed
docker compose -f vendor-shadybank/docker-compose.yml down -v && \
docker compose -f vendor-shadybank/docker-compose.yml up -d db redis api-endpoint
# our app DB
docker exec -i shadypredict-db psql -U shadypredict -d shadypredict \
  -c "TRUNCATE deposits, sessions, ledger_entries, ledger_tx, users, ledger_accounts RESTART IDENTITY CASCADE;"
```
