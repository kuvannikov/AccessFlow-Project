.PHONY: up down logs ps migrate check backend-check test-keycloak

check: backend-check

backend-check:
	cd backend && uv lock --check
	cd backend && uv run --frozen ruff check .
	cd backend && uv run --frozen ruff format --check .
	cd backend && uv run --frozen mypy
	cd backend && uv run --frozen lint-imports
	cd backend && uv run --frozen pytest

test-keycloak:
	cd backend && uv run --frozen pytest -m keycloak

up:
	docker compose up -d --wait --wait-timeout 180

# Never add -v here: it deletes the database.
down:
	docker compose down

logs:
	docker compose logs -f --tail=100

ps:
	docker compose ps

# Apply the migrations to the dev database as the schema owner. The API's own
# connection settings come from .env; only the role and its password change.
migrate:
	cd backend && uv run --frozen --env-file ../.env sh -c \
		'ACCESSFLOW_DATABASE_USER=accessflow_owner ACCESSFLOW_DATABASE_PASSWORD="$$ACCESSFLOW_OWNER_PASSWORD" alembic upgrade head'
