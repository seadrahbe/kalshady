# ShadyPredict — Onboarding / Handoff

A satirical **Kalshi-style prediction market** that runs on **ShadyBucks** (the ToorCamp event
currency, served by the open-source `Shadytel/shadybank`). Users bet ShadyBucks on yes/no
questions; the house takes a 30% rake. **Backend is the core of this repo; the frontend is a
Vite/React Kalshi look-alike we integrated.**

Deep design + history: see **`PLAN.md`**. How to run everything: **`DEV.md`**. This file is the
quick orientation.

---

## What it does (the money loop)
`sign in (PAN+OTP) → deposit → bet → live odds → admin resolves → payout → end-of-event cash-out`

- **Parimutuel pools**: each outcome has a pool; a bettor's payout = their share of the winning
  pool × (total pool − rake). Self-funding — the house never risks its own bucks.
- **Deposit = PUSH**: the user's own bank token (from login) `credit`s the house account — no
  per-deposit OTP. Money then lives in an **internal wallet**; betting is internal/instant.
- **Display odds can be set manually by the admin** (the "Set odds" control / `outcome_prices`).
  These are **display only** — payouts are always parimutuel on the *real* pools.
- **Cash-out** (end of event): the house pays every wallet back to its card via `credit`,
  authenticated with a **house OTP the admin types in** (no stored house PIN on the live bank).

## Architecture
- **Backend** (`app/`): Python **FastAPI** + **PostgreSQL** (SQLAlchemy 2.0 async) + **Alembic**.
  Double-entry ledger (`app/ledger.py`, accounts `EXTERNAL/HOUSE/USER/POOL`). Talks to shadybank
  only at deposit + cash-out via `bank/client.py`. OpenAPI at `/openapi.json`, docs at `/docs`.
- **Frontend** (`vendor-kalshady/frontend/`): Vite + React. `src/api.js` (API client),
  `src/App.jsx` (auth gate, balance, deposit, routing, polling), `src/views/pages/Market.jsx`
  (markets + betting), `src/views/pages/Admin.jsx` (`/admin` console). Talks to the backend at
  `VITE_API_URL` (default `http://localhost:8010`).
- **shadybank** (`vendor-shadybank/`): the money rail, run locally via docker-compose for dev.

## Key endpoints
- Auth: `POST /api/auth/login` {pan, otp} → `{session_token, user, wallet}`, `GET /api/auth/me`, `/logout`
- Wallet: `GET /api/wallet`, `POST /api/wallet/deposit` {amount_cents, idempotency_key}
- Markets: `GET /api/markets`, `/{id}`, `POST /{id}/bet`, `GET /{id}/position|history|trades|stream`(SSE)
- Portfolio: `GET /api/portfolio`
- Admin (header `X-Admin-Key`): `GET /api/admin/check`, `POST /api/admin/markets`,
  `/{id}/odds` `/open` `/close` `/resolve` `/void`, `POST /api/admin/cashout` {otp},
  `GET /api/admin/reconcile?otp=`, `GET /api/admin/cashouts`

## Run it (summary — full detail in DEV.md)
Ports: shadybank `:8021`, our Postgres `:5433`, backend `:8010`, frontend `:5173`.
```bash
# 1. shadybank (local dev money rail)
cd vendor-shadybank && docker compose up -d db redis api-endpoint   # wait for /api/balance -> 401
docker compose -f vendor-shadybank/docker-compose.yml exec -T db psql -U shadybucks -d shadybucks < seed.sql
# 2. our Postgres
docker run -d --name shadypredict-db -e POSTGRES_USER=shadypredict -e POSTGRES_PASSWORD=shadypredict \
  -e POSTGRES_DB=shadypredict -p 5433:5432 postgres:16
# 3. backend  (Python 3.13 venv; see DEV.md)
./.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8010
# 4. frontend
cd vendor-kalshady/frontend && npm install && npm run dev   # http://localhost:5173 ; admin at /admin
```
Tests (against LOCAL bank only): `scripts/test_backend.py`, `test_markets.py`, `test_resolution.py`,
`test_phase4.py`, `test_phase5.py`. Helper: `scripts/show_markets.py`.

## Config & secrets
All config is env vars (`SP_*`) read from **`.env`** (gitignored — NOT in this repo). Get values
from the project owner. Notable ones:
- `SP_BANK_API_URL` — local `http://127.0.0.1:8021` for dev, `https://bucks.shady.tel` for live.
- `SP_HOUSE_PAN` — the ShadyBucks account deposits land in (live house account).
- `SP_ADMIN_KEY` — the `/admin` password.
- `SP_FERNET_KEY` — encrypts stored bank tokens. `SP_AUTO_CREATE_TABLES` — dev table bootstrap.
- House cash-out uses a **runtime OTP** (admin-entered), not a stored PIN.
- `.env.live` (gitignored) holds a real card for the read-only `scripts/live_smoke.py`.

## Decisions locked in
Backend-only build (this team) + a provided frontend; parimutuel pools; PUSH deposit → wallet →
cash-out only at event end; PAN+OTP login; **30% rake** default; **min bet 10 SB**, no max, no
deposit caps; manual display odds (payouts still parimutuel); custom build borrowing
play-money's typed-account ledger.

## Current status
Backend complete (Phases 0–5, all test suites green): bank integration, wallet/deposit, markets +
parimutuel betting + live odds, resolution/payout/cash-out, hardening (Alembic, login throttle,
reconciliation, concurrency-safe betting). Frontend integrated: login, deposit, betting, live
polling, and a password-gated `/admin` (create questions, set odds, resolve/void, cash-out).
**Backend is currently pointed at the LIVE bank** (real bucks move on deposit/cash-out).

## Gotchas (will bite you)
- **Don't run the local money-moving test scripts while `.env` points at the live bank** — they
  use local test cards and will fail login (or hit prod). Point `SP_BANK_API_URL` back to
  `:8021` for local testing.
- **asyncpg caches query plans**: if you DROP/recreate the DB schema under a running server,
  **restart uvicorn** or you'll get 500s.
- **Frontend circular import**: don't reference the palette `C` (from `App.jsx`) at *module top
  level* in a child module — it's in the temporal dead zone during load and white-screens the
  app. Use `C` inside components only. (The prod build hides this; the dev server catches it.)
- **OTP rate limit** on the bank is 5/600s per card — login burns one; design around it.
- shadybank on Apple Silicon: api service runs under `linux/amd64` emulation; postgres pinned 16.

## Likely next steps
Deploy beyond localhost (e.g., a small always-on VM), tighten prod config (real `SP_ADMIN_KEY`,
`SP_COOKIE_SECURE=true`, `SP_AUTO_CREATE_TABLES=false`, restrict CORS), optionally hide
resolved/void markets from the main page, and decide whether manual odds should ever drive
*payouts* (fixed-odds — adds house risk) vs the current display-only behavior.
