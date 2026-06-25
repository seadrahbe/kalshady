# ShadyPredict — Build Plan

A satirical prediction market that runs on **ShadyBucks** (event currency), using the
open-source [shadybank](https://github.com/Shadytel/shadybank) as the money rail.

---

## 1. Core design decisions

### Market model: parimutuel pools with live "indicative odds"
- Each market is a question with 2+ outcomes (usually YES / NO).
- Users bet ShadyBucks into the pool for an outcome.
- **Live odds** shown on the site = current pool share:
  `price(outcome) = outcome_pool / total_pool` → displayed as cents/% (e.g. 64¢ ≈ 64%).
  This number moves in real time as bets come in — looks exactly like Kalshi.
- **Payout is parimutuel**, locked at close, not at bet time:
  `payout(user) = user_stake_on_winner × (total_pool × (1 − rake)) / winning_pool`
- Why this model: **zero house risk** (you only ever pay out money already collected),
  **no liquidity problem** (a bet into a pool always "fills" — unlike a Kalshi order book,
  which would sit empty with only ~500 users).

### Money architecture: deposit → internal wallet → withdraw
This is the single most important decision. We do **NOT** call shadybank on every bet.

- **Correction (verified in source):** any account can move money — `/api/credit` requires NO
  merchant flag and is exposed to every logged-in user via the bank's `/app/transact` page
  (`frontend.py post_transact`). So `credit` is effectively a **peer-to-peer push transfer**,
  and **any account can act as our "house"** — we do NOT need an operator-issued merchant
  account (operator OK is now a policy/social matter, not a technical gate).
- **DEPOSIT MODEL = PUSH (decided).** At login we keep the bettor's bank token for their session;
  a deposit is our backend calling `/api/credit` with the **bettor's own token** to send bucks to
  the house PAN. `credit` needs **no OTP** → one OTP at login, then friction-free deposits.
  - **Mandatory mitigations** (because that token can move the user's whole bank balance): store
    bank tokens **server-side only, encrypted at rest, never sent to the client**; short session
    TTL; logout invalidates; restrict/log every code path that uses a user token.
- The deposit then credits an **internal wallet** in our own DB; all betting is internal ledger
  movement (instant, no bank call, no OTP).
- (PULL — house `authorize`+`capture` with a per-deposit OTP — was the safer alternative we
  considered; rejected in favor of PUSH's smoother UX.)
- **Cash out only at the end** (decided): withdrawals are **disabled during the event**. When
  the admin closes the event, every wallet is paid back to its card via `credit` in one
  settlement pass. This removes float complexity entirely — but note it creates a **burst of
  ~500 `credit` calls at event end**, which must be **batched/queued** against the bank's rate
  limits (see Phase 5). During the event, the bank is only touched by deposits.
- Invariant: `Σ(user wallet balances) + Σ(open pools) + house_rake_collected ≤ house account balance`.

This isolates the shadybank dependency to two flows (deposit, withdraw) and makes the market
itself fast, self-contained, and easy to test.

### House (merchant) account
- One shadybank account acts as the house. It holds all deposited funds in escrow.
- For pure parimutuel + deposit-model + cash-out-at-end, the house **never goes negative**, so
  the `special`/`partner` overdraft flag is **not required**.

### Admin authority (decided)
- The admin (event organizer) **decides the result of every question**. There is no external
  data feed or oracle — resolution is a manual admin action. The admin console is therefore a
  first-class part of the app, not an afterthought: create/edit markets, open/close betting,
  pick the winning outcome, void a market, and trigger end-of-event settlement.

### UI: Kalshi look-alike (decided — this is satire)
The UI must visually read as Kalshi. Clone the layout and feel, not the brand:
- **Market grid** (home): cards showing the question, a green **YES** / red **NO** with **cent
  prices** (e.g. `64¢`), the implied **%**, a mini sparkline, and volume.
- **Market detail:** big **probability-over-time chart**, a Kalshi-style **"trade ticket"**
  panel (here: YES/NO toggle + bet amount + projected payout-if-win), and an expandable
  "rules/resolution" section.
- **Portfolio/positions** page and a **top nav showing wallet balance**.
- **Aesthetic:** clean light theme, Kalshi's mint/teal accent, green/red for YES/NO, lots of
  whitespace and cards. Swap in satirical ShadyTel/Beerocracy copy and logo.

### Scope: BACKEND ONLY (decided)
- We build the **backend** — the market engine, ledger, shadybank integration, admin actions —
  and expose it as a **documented JSON API**. A separate team builds the Kalshi-look UI against
  our contract.
- This makes the **API contract a first-class deliverable**: publish an **OpenAPI spec** (FastAPI
  generates it) and stand up the API early so the UI team can develop in parallel against it (or
  a mock). The Kalshi-UI spec above (cards, prices, trade ticket, charts) is now **requirements
  for that team** + a checklist of the data our endpoints must return (cent prices, implied %,
  price history, positions, projected payout).
- The former "Phase 4 — Kalshi UI" is **out of our scope**; our Phase 4 becomes the data/endpoints
  that make it possible (price-history endpoint, live-odds polling/SSE, positions).

### Tech stack
- **Backend:** Python + FastAPI (matches shadybank's ecosystem; async fits the bank client;
  auto-generates the OpenAPI spec the UI team needs).
- **DB:** PostgreSQL (own instance, separate from shadybank's).
- **Frontend:** out of scope — built by another team. We hand off an OpenAPI spec + a running API.
- **Live odds:** default to **2–3s polling** (works on any host, including serverless);
  upgrade to **SSE** only if the host supports long-lived connections (the VM option below does).

### Hosting (decided: self-host, free)
Goal: free, **always-on** (no cold start — bad during a live event), able to make outbound HTTP
to the bank, and able to hold a Postgres DB + (optionally) the self-hosted shadybank stack.

- **Recommended: Oracle Cloud "Always Free" VM.** A genuinely-free, always-on Linux VM (ARM
  Ampere, up to 4 vCPU / 24 GB) big enough to run **everything via docker-compose on one box** —
  the market app, its Postgres, and even shadybank itself. No sleep, supports SSE/WebSockets.
  Caveats: credit-card identity check at signup, ARM architecture, occasional regional capacity
  limits when claiming an instance.
- **Acceptable alternatives:** Railway / Render / Fly.io (container hosts that support
  SSE/WebSockets) — but in 2026 their free always-on tiers are gone/limited, so expect ~$5/mo.
  Free **Postgres** can come from **Neon** or **Supabase** (note: they pause on inactivity).
- **Avoid for the backend:** Vercel / Netlify / Cloudflare Workers — serverless, **cannot host
  SSE/WebSockets** and cold-start. Fine for a static frontend only.

### Scale note
500 users is trivial infrastructure-wise. The real constraints are (a) **shadybank rate
limits** — concentrated at deposit time and the **end-of-event cash-out burst** (handled by a
queue/batcher), and (b) **money correctness** under concurrency (DB transactions + row locks +
idempotency keys).

---

## 2. Data model (sketch)

```
users(id, shadybank_account_id, name, pan_token (encrypted), created_at)

-- Ledger (typed-account double-entry, borrowed from play-money's design):
accounts(id, type[USER|HOUSE|MARKET_POOL], user_id?, market_id?, outcome_id?)
tx(id, type, created_at)                              -- a transaction groups entries
tx_entry(id, tx_id, amount_cents, from_account_id, to_account_id)  -- atomic, one DB txn
-- A user's spendable balance = SUM(entries to their account) - SUM(entries from it).
-- Optional materialized balances(account_id, balance_cents) for fast reads, rebuilt from entries.
deposits(id, user_id, amount_cents, bank_auth_code, status, idempotency_key, created_at)
withdrawals(id, user_id, amount_cents, bank_ref, status, idempotency_key, created_at)
markets(id, title, description, status[open|closed|resolved|void], rake_bps, closes_at, resolved_outcome_id)
outcomes(id, market_id, label, pool_cents)
bets(id, market_id, outcome_id, user_id, stake_cents, created_at)
odds_snapshots(market_id, outcome_id, price_bps, ts)  -- for the price-history chart
```
Money is stored as **integer cents** everywhere (shadybank is `numeric(8,2)`); convert only at
the bank boundary.

### Key formulas
- Indicative price (bps): `outcome.pool_cents * 10000 / total_pool_cents`
- Payout per winning bet: `stake_cents * (total_pool_cents * (10000 - rake_bps) / 10000) / winning_pool_cents`,
  rounded down to cents; distribute the leftover remainder cents deterministically (largest-remainder).

---

## Progress
- **Phase 0 — DONE.** shadybank self-hosted locally (`vendor-shadybank/`); `bank/client.py` async
  client; deposit→cash-out round-trip + P2P push verified. See `DEV.md`.
- **Phase 1 — DONE (core).** FastAPI backend (`app/`) on Postgres: "Sign in with ShadyBucks"
  (PAN+OTP, bank token kept server-side encrypted), PUSH deposit → internal wallet, typed-account
  double-entry ledger, idempotent deposits, OpenAPI at `/openapi.json`. Verified by
  `scripts/test_backend.py` (incl. real bank money movement). TODO: Alembic migrations, withdrawals
  table wiring (cash-out is Phase 3), reconciliation job (Phase 5).
- **Phase 2 — DONE.** Markets/outcomes/bets + POOL ledger accounts; admin create/open/close
  (`X-Admin-Key`); public market list/detail with live parimutuel odds (pool share as ¢/%);
  bet placement (wallet→pool, atomic with row lock, idempotent); positions + projected payout.
  Live bank confirmed reachable (`scripts/live_smoke.py`). Verified by `scripts/test_markets.py`.
- **Phase 3 — DONE.** Admin resolve (parimutuel payout: drain pools→HOUSE, pay winners by
  largest-remainder split, HOUSE keeps the rake), void/refund, and end-of-event cash-out
  (`/api/admin/cashout`: every wallet `credit`ed back to its card via the house token, durable
  per-user CashOut rows). `app/resolution.py`, `app/cashout.py`. Verified end-to-end (deposit→
  bet→resolve→payout→cash-out, balancing to the cent incl. rake) by `scripts/test_resolution.py`.
- **Phase 4 — DONE.** Live-odds data for the UI: `odds_snapshots` written on create + each bet;
  `GET /api/markets/{id}/history` (price chart), `/trades` (ticker), `/stream` (SSE live odds),
  and `GET /api/portfolio` (cross-market positions). `scripts/test_phase4.py` verifies all incl. SSE.
- **Phase 5 — DONE.** Hardening: **Alembic** migrations (`alembic/`, baseline applied; dev
  `create_all` gated by `SP_AUTO_CREATE_TABLES`); **min-bet floor** 10 bucks (no max, no deposit
  cap); **login throttle** (`app/ratelimit.py`); **reconciliation** (`app/reconcile.py`,
  `GET /api/admin/reconcile` — ledger↔bank `sp:*` tag match + money-sum + overspend/solvency check);
  cash-out is re-runnable/retryable (`GET /api/admin/cashouts`). `scripts/test_phase5.py` verifies
  min-bet, throttle (429), **20-way concurrent overspend safety (row lock holds)**, and reconcile.

## Status: backend complete (Phases 0–5), all test suites green. Remaining = prod config
(tighten CORS, real `SP_ADMIN_KEY`, `SP_COOKIE_SECURE=true`, `SP_AUTO_CREATE_TABLES=false`),
deploy, and a true multi-card 500-user load test at the venue. UI is the separate team's build.

## 3. Phased build

### Phase 0 — Integration spike (de-risk the bank) ⚠️ do this first
**Goal:** prove the money rail works end-to-end before building anything else.
- Self-host shadybank via its `docker-compose.yml`; load `srv/data/testdata.sql`.
- Identify/create a **house merchant account** and a couple of **test customer cards**.
- Build a thin async `ShadyBankClient`: `login`, `balance`, `transactions`, `authorize`,
  `capture`, `void`, `reverse`, `credit`.
- Manually run a full round-trip: charge a test card (`authorize`+`capture`) → confirm money
  lands in house account → `credit` it back. Confirm OTP behavior and rate limits firsthand.

**Exit criteria:** a script that deposits from a test card and withdraws back, verified in the
bank's `/api/balance` and `/api/transactions`.

### Phase 1 — Accounts, wallet, deposit (no markets yet)
**Goal:** users can sign in with their card and deposit ShadyBucks into an internal wallet.
- Schema: `users`, `wallets`, `ledger`, `deposits`, `withdrawals` (withdrawals table built now,
  but the flow is gated until event end — see Phase 3).
- **"Sign in with ShadyBucks":** card# (PAN) + **OTP** → shadybank `/api/login` → on success
  call `/api/balance` to get `account`+`name` → mint our own session cookie/JWT. **Keep the
  bank token server-side (encrypted)** for the session — the PUSH deposit model uses it to
  `credit` the house (do NOT drop it; do NOT expose it to the client). Store
  `shadybank_account_id`, `name`, and the **PAN encrypted** (needed for end-of-event `credit`).
  - **Why OTP, not PIN:** PAN+OTP is the *native* shadybucks login (this is exactly what the
    bank's own `frontend.py` / `bucks.shady.tel` uses), and every ToorCamp attendee already has
    an OTP source. PIN is an *optional* secret in shadybank, so PIN login would fail for many
    cards. (Earlier draft said PIN — corrected after reading the source + ToorCamp wiki.)
  - Session is long-lived so OTP is entered **once per session** for browsing/betting, not per
    page. Each deposit prompts for a fresh OTP. Typical usage = 1 (login) + 1/deposit, well
    under the bank's 5-OTP / 600s limit. Add our own login throttling anyway.
- **Deposit flow:** amount + **OTP** → `authorize`+`capture` into house → credit internal wallet.
  Idempotency key to prevent double-charge on retry. (A booth magstripe swipe needs no OTP — the
  physical path the event already uses for merchants.)
- Wallet/balance page. Reconciliation check (internal balances vs house account).

**Exit criteria:** a real user can deposit 50 bucks and see balance 50; the house account and
bank ledger match; money invariant holds. (Cash-out is exercised in Phase 3.)

### Phase 2 — Markets, parimutuel betting, live odds + Kalshi market UI
**Goal:** the actual market, with Kalshi-style live prices and the Kalshi-look market pages.
- Schema: `markets`, `outcomes`, `bets`; `odds_snapshots`.
- **Admin console (v1):** create market + outcomes, set rake, open/close betting, set `closes_at`.
- **Place bet:** internal ledger move (wallet → outcome pool) inside a DB transaction with row
  locking. No bank call.
- **Live indicative odds:** compute `price = pool / total_pool` per outcome; render as ¢/%.
- **Kalshi-clone UI:** market-card grid (home) + market detail with the YES/NO trade ticket,
  amount entry, and projected payout-if-win. Functional styling now; polish in Phase 4.

**Exit criteria:** multiple users bet on a market from their wallets via the Kalshi-style ticket;
odds update live and sum to ~100%; pools and wallets stay consistent.

### Phase 3 — Admin resolution, payout & end-of-event cash-out
**Goal:** admin settles markets, winnings land in wallets, everyone cashes out at the end.
- **Admin resolves** the winning outcome (or voids) — manual decision, no oracle.
- Parimutuel payout: integer-cents math, apply rake, largest-remainder distribution of leftover
  cents; credit winners' **internal wallets**; write `ledger` entries.
- **Void/refund path:** return each bettor's stake to their wallet.
- Edge cases: nobody bet the winning side → refund everyone; single-sided market → refund.
- **End-of-event cash-out:** admin "close event" action → for every wallet with a balance,
  `credit` it back to the stored card. Process as an **idempotent, queued batch** (rate-limit
  aware — see Phase 5) with a per-user status (pending/sent/failed + retry).
- Settlement audit log per market and for the cash-out run.

**Exit criteria:** resolve a market end-to-end; total paid out = pool − rake (to the cent);
running "close event" cashes out all wallets to the bank with every transfer reconciled; audit
log balances.

### Phase 4 — Live-odds data + API endpoints for the UI team (backend side of the Kalshi UI)
**Goal:** expose everything the UI team needs to render the Kalshi look. We build data, not pixels.
- Price-history endpoint per outcome from `odds_snapshots` (feeds Kalshi's signature graph).
- Live updates: polling endpoints by default; **SSE** stream if the host supports it.
- Endpoints returning exactly what the cards/ticket/portfolio need: cent prices, implied %,
  pool sizes, recent trades, a user's positions + projected payout-if-win, leaderboard.
- Finalize and publish the **OpenAPI spec**; provide a seeded demo dataset/mock for the UI team.

**Exit criteria:** the OpenAPI spec covers every screen in the UI requirements; a frontend dev can
build the Kalshi UI against our running API without backend changes; live odds poll/stream cleanly.

### Phase 5 — Hardening for ~500 users
**Goal:** correct and robust under real event load.
- DB transactions + `SELECT ... FOR UPDATE` on every wallet/pool mutation.
- **Idempotency keys** on deposit/withdraw (network retries must not double-charge).
- shadybank **rate-limit handling**: backoff + a small serialized queue for `authorize`
  (3/30s merchant limit) and OTP (5/600s); surface clear "try again" UX.
- **End-of-event cash-out batcher:** the ~500 `credit` calls must drain through the bank's rate
  limits without losing or double-sending any — durable queue, idempotency keys, per-transfer
  status, automatic retry, and an admin view of progress/failures.
- Money-invariant reconciliation job + admin dashboard; alert on drift.
- Abuse limits (min/max bet, deposit caps), structured logging, error pages.
- Load test ~500 concurrent users (betting is internal so this is easy; focus the load test on
  the deposit path and the cash-out burst against the bank's limits).
- Deployment: docker-compose with bank + market + Postgres on the Oracle Always-Free VM; backups.

**Exit criteria:** simulated 500-user session with no money drift, graceful rate-limit handling,
clean recovery from mid-deposit failures, and a full cash-out batch that reconciles to the cent.

---

## 4. Decisions locked in
- **Hosting:** self-hosted, free → Oracle Cloud Always-Free VM (docker-compose).
- **Cash-out:** only at event end (no mid-event withdrawals).
- **Resolution:** admin manually decides every question's result.
- **UI:** Kalshi look-alike (satire).
- **Model:** parimutuel pools with live indicative odds.

## 4a. Prior art / build-vs-fork (from GitHub research)
- **Context:** shadybucks is the **ToorCamp** event currency (per the ToorCamp wiki) — wristband
  + magstripe card per attendee, transacting at `bucks.shady.tel`. Physical acceptance is via
  **magstripe reader**; browser NFC is not viable.
- **Reusable OSS markets:**
  - [`casesandberg/play-money`](https://github.com/casesandberg/play-money) — TS/Next.js/Prisma/
    Postgres, **MIT**, self-hostable, has accounts/markets/leaderboards. Best fork candidate;
    needs a code read to confirm its currency layer is separable enough to swap for a
    shadybank-backed wallet.
  - [`greggles/pmb`](https://github.com/greggles/pmb) — parimutuel but Drupal 7 (EOL), skip.
  - Manifold — full-featured CPMM, open source, but heavy/expensive; overkill.
- **DECISION (after reading the code): build custom, borrow play-money's ledger design.**
  - play-money's engine is **Maniswap (a CPMM/AMM)**, and its economy is **inflationary by
    design** — 20k minted per signup, daily bonuses, and 500 house-funded liquidity per market
    (`economy.ts`). That directly violates our invariant (*internal supply == real bucks
    escrowed*), so a full fork would mean gutting its economy + funding AMM liquidity with real
    bucks (reintroducing house float/risk). Not worth it.
  - **Borrow its ledger, though:** typed-account double-entry — accounts `USER | HOUSE |
    MARKET_POOL`; `TransactionEntry(amount, asset, fromAccount→toAccount)`; all entries written
    atomically in one DB transaction (`executeTransaction`). This maps cleanly onto our flows
    and makes cash-out **solvent by construction** (money enters only via real deposits, leaves
    only via real withdrawals).
  - **Fork reconsidered only if** we decide we want the AMM UX (live buy *and sell* / exit
    before resolution) and accept a bounded house float seeded from a rake — a product decision.

## 5. Open questions still to resolve before/early in Phase 0
1. **Which bank instance?** We self-host the *market app* — but does it point at the real
   `bucks.shady.tel`, or our own self-hosted shadybank? The live one needs a merchant account
   + operator (ShadyTel/Beerocracy) sign-off. (Dev: always against a local self-hosted bank.)
2. **Rake / house cut** — take a satirical "vig" or 0%?
3. **Deposit channel** — purely self-serve web (PAN + OTP on a phone, which we now know every
   attendee can do), or also a staffed **magstripe booth** (swipe = no OTP needed)? Web-only is
   the simplest v1 and needs no hardware.
4. **Dispute handling** — admin decision is final, or is there an appeal/announcement flow?
5. **Build vs fork** — confirmed in Phase 0 after reading `play-money`'s ledger code.
