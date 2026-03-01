#!/usr/bin/env bash
# Очистка всех таблиц в БД, кроме users.
# Запуск из корня репозитория: ./scripts/truncate-except-users.sh

set -e
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
COMPOSE_FILE="$REPO_ROOT/infra/docker/docker-compose.yml"

cd "$REPO_ROOT"
docker compose -f "$COMPOSE_FILE" exec -T db psql -U analyst_user -d analyst_db <<'SQL'
DO $$
DECLARE
  r RECORD;
BEGIN
  FOR r IN (
    SELECT tablename
    FROM pg_tables
    WHERE schemaname = 'public'
      AND tablename != 'users'
  )
  LOOP
    EXECUTE format('TRUNCATE TABLE %I CASCADE', r.tablename);
  END LOOP;
END $$;
SQL
echo "Done: all tables truncated except users."
