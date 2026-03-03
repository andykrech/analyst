# ruff: noqa
# pylint: skip-file

cd infra/docker && docker compose up --build -d
docker compose -f infra/docker/docker-compose.yml logs -f
cd frontend/web && npm run dev

source backend/.venv/Scripts/activate

docker compose exec backend alembic revision --autogenerate -m "Add users table"

docker compose exec backend alembic upgrade head

https://ifconfig.me / получение текущего ip адреса

# очистка всей базы данных, кроме таблицы users
docker compose exec -T db psql -U analyst_user -d analyst_db < ../../scripts/truncate-except-users.sql
# очистка версии извлечения сущностей из квантов (для повторения поиска сущностей)
docker compose exec db psql -U analyst_user -d analyst_db -c "UPDATE theme_quanta SET entity_extraction_version = NULL;"