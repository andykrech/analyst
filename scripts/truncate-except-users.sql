-- Очистка всех таблиц в схеме public, кроме users.
-- В контейнере: psql -U analyst_user -d analyst_db -f truncate-except-users.sql

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
