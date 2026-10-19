# AccessFlow

Web platform for employee onboarding and offboarding driven by configurable business processes.

## Status

Rebuild in progress. The application is being rebuilt from scratch, so setup and usage instructions will be added as the work progresses.

## Local infrastructure

PostgreSQL and Keycloak run in Docker Compose. All ports are bound to
`127.0.0.1`, so the services are reachable only from your machine.

### Requirements

- Docker with Compose v2 (`docker compose version`)
- GNU Make

### First start

1. Create your environment file and fill in every value
   (generate a password with `openssl rand -hex 24`):

   ```bash
   cp .env.example .env
   ```

2. Start the services and wait until both are healthy:

   ```bash
   make up
   ```

### Services

| Service    | Address                 | Notes                                                        |
|------------|-------------------------|--------------------------------------------------------------|
| PostgreSQL | `127.0.0.1:5432`        | Databases `accessflow` and `keycloak`                        |
| Keycloak   | `http://localhost:8081` | Admin console, user `admin`, password `KEYCLOAK_ADMIN_PASSWORD` |

The realm `accessflow` is imported on the first start. Its OpenID Connect
discovery document is at
`http://localhost:8081/realms/accessflow/.well-known/openid-configuration`.

PostgreSQL roles:

| Role               | Purpose                                              |
|--------------------|------------------------------------------------------|
| `accessflow_owner` | Owns the `accessflow` database, runs migrations      |
| `accessflow_app`   | Used by the API at runtime, data access only         |
| `keycloak`         | Owns the `keycloak` database, used by Keycloak       |

### Commands

| Command      | What it does                                                    |
|--------------|-----------------------------------------------------------------|
| `make up`    | Start the services and wait until they are healthy              |
| `make down`  | Stop and remove the containers; the data volume is kept         |
| `make ps`    | Show the state of the services                                  |
| `make logs`  | Follow the logs (stop with Ctrl+C)                              |
| `make check` | Lint, format check, types and tests of the backend              |

### Data

The database lives in the Docker volume `accessflow_postgres_data` and
survives `make down`. Do not run `docker compose down -v` or
`docker volume rm`: they delete all data irreversibly.

Passwords from `.env` are applied only when the database is created.
Changing them later does not change the passwords of existing roles.

## Backend

The API is a Python project in `backend/`, managed by [uv](https://docs.astral.sh/uv/).
The Python version is pinned in `backend/.python-version`, and the dependency
versions are pinned in `backend/uv.lock`.

### Setup

```bash
cd backend
uv sync --frozen
```

`--frozen` installs exactly the versions from `uv.lock` and never changes it.

### Run

The API needs one environment variable, `ACCESSFLOW_ENVIRONMENT`
(`development`, `test` or `production`). Without it the application refuses
to start. The variable is read from the process environment, not from `.env`.

```bash
cd backend
ACCESSFLOW_ENVIRONMENT=development uv run --frozen uvicorn accessflow.app:create_app \
  --factory --host 127.0.0.1 --port 8000
```

Check that it is alive:

```bash
curl -i http://127.0.0.1:8000/api/health
```

The answer is `200 OK` with the body `{"status":"ok"}`.

### Checks

Run from the repository root:

```bash
make check
```

It runs Ruff (lint and format check), mypy in strict mode and pytest. Warnings
raised during tests are treated as errors.
