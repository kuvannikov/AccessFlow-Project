.PHONY: up down logs ps check backend-check

# Run every check of the project (the frontend joins later).
check: backend-check

# Lint, format check, types and tests of the backend.
backend-check:
	cd backend && uv run --frozen ruff check .
	cd backend && uv run --frozen ruff format --check .
	cd backend && uv run --frozen mypy
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
