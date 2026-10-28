.PHONY: up down logs ps migrate check backend-check

# Run every check of the project (the frontend joins later).
check: backend-check

# Lint, format check, types, module boundaries and tests of the backend.
backend-check:
	cd backend && uv run --frozen ruff check .
	cd backend && uv run --frozen ruff format --check .
	cd backend && uv run --frozen mypy
	cd backend && uv run --frozen lint-imports
	cd backend && uv run --frozen pytest

# Start the dev stack and wait until both services are healthy.
up:
	docker compose up -d --wait --wait-timeout 180

# Stop and remove containers and the network. Volumes (the data) are kept.
# Never add -v here: it deletes the database.
down:
	docker compose down

# Follow the logs of all services (stop with Ctrl+C).
logs:
	docker compose logs -f --tail=100

# Show the state of the services.
ps:
	docker compose ps

# Apply the migrations to the dev database as the schema owner. The API's own
# connection settings come from .env; only the role and its password change.
migrate:
	cd backend && uv run --frozen --env-file ../.env sh -c \
		'ACCESSFLOW_DATABASE_USER=accessflow_owner ACCESSFLOW_DATABASE_PASSWORD="$$ACCESSFLOW_OWNER_PASSWORD" alembic upgrade head'
