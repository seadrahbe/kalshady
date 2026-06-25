#!/usr/bin/env bash
# Phase 0 runner: wait for shadybank to be reachable, (re)seed test fixtures,
# then run the deposit -> cash-out round-trip test.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE="$ROOT/vendor-shadybank/docker-compose.yml"
DB_SVC="db"
API="http://127.0.0.1:8021"

echo ">> Waiting for shadybank API at $API ..."
# /api/balance without a token returns 401 quickly once the app is serving.
until curl -sS -m 5 -o /dev/null -w '%{http_code}' "$API/api/balance" 2>/dev/null | grep -qE '401|400|405'; do
  printf '.'; sleep 2
done
echo " up."

echo ">> Seeding test fixtures (idempotent wipe of prior ShadyPredict test rows)..."
# Wipe any prior test rows so re-runs start clean, then load seed.sql.
docker compose -f "$COMPOSE" exec -T "$DB_SVC" psql -U shadybucks -d shadybucks <<'SQL'
DELETE FROM secrets WHERE account_id IN (SELECT id FROM accounts WHERE name IN ('Test Bettor','ShadyPredict House'));
DELETE FROM cards   WHERE pan IN ('8997000000000001','8997000000000002');
DELETE FROM accounts WHERE name IN ('Test Bettor','ShadyPredict House');
DELETE FROM customers WHERE name = 'Test Bettor';
SQL
docker compose -f "$COMPOSE" exec -T "$DB_SVC" psql -U shadybucks -d shadybucks < "$ROOT/seed.sql"

echo ">> Running round-trip test..."
"$ROOT/.venv/bin/python" "$ROOT/scripts/test_roundtrip.py"
