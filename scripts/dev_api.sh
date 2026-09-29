#!/usr/bin/env bash
set -euo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
set -a
source "$project_dir/.env"
set +a

export DATABASE_URL="postgresql+psycopg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@localhost:5432/${POSTGRES_DB}"
export OIDC_ISSUER="http://localhost:8081/auth/realms/accessflow"
export OIDC_JWKS_URL="http://localhost:8081/auth/realms/accessflow/protocol/openid-connect/certs"
export OIDC_AUDIENCE="accessflow-api"

cd "$project_dir/backend"
uv run alembic upgrade head
exec uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000 --no-access-log
