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
  --factory --host 127.0.0.1 --port 8000 --no-access-log
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

### Errors and request diagnostics

Every HTTP response includes `X-Request-ID`. Send one canonical UUID in this
header to reuse it (uppercase is normalized); a missing, malformed or repeated
header is replaced with a new UUID. This identifier connects the response to
its HTTP log record. It is not an authentication credential.

Errors use `application/problem+json`, following
[RFC 9457](https://www.rfc-editor.org/rfc/rfc9457.html). For example:

```json
{
  "type": "/problems/validation.failed",
  "title": "Validation failed",
  "status": 422,
  "code": "validation.failed",
  "requestId": "94801dde-c1c2-405a-894b-749617848fd9",
  "errors": [{"field": "displayName", "code": "invalid"}]
}
```

Use `code` for program decisions, not the English `title`. Validation returns
only declared top-level field aliases and the safe code `invalid`. Unknown
locations receive no `field`; nested submitted keys and validator messages are
never exposed. Submitted values, `input`, `ctx` and exception details are omitted.
Malformed JSON, invalid UTF-8, unpaired Unicode surrogates and non-finite JSON
numbers return 422 `request.invalid_body`. JSON bodies are checked before
routing when the media type is `application/json`, `application/*+json` or
absent. Other content types remain subject to endpoint validation.

An unexpected error returns 500 with only `code: "internal"` and `requestId`.
Business modules can subclass `core.errors.DomainError` and register a
`ProblemDefinition` in `app.state.error_registry`. The public definition is
fixed by the module; the exception message is never serialized. An unregistered
error is internal. Standard HTTP errors preserve protocol headers such as
`Allow` and `WWW-Authenticate`, but omit their original detail.

Each request produces one `key=value` line with UTC time, level, `request_id`,
method, route template, status and `duration_ms`. Unmatched routes use
`unmatched`; logs contain no raw path, query string, headers, body or exception
text. An unhandled exception adds `error` (its type) and `origin` (the file and
line where it was raised). Uvicorn's default access logger is disabled by the application; keep
`--no-access-log` in launch commands as well. Server exception logs omit
tracebacks and preserve the request ID for failures after a response starts.
Do not enable a second HTTP access logger with raw URLs or body logging.
These operational logs are not a business audit trail.

If a streamed response has already started, HTTP cannot replace its status or
body with a 500 problem. The stream fails, and its original status is logged
at ERROR with the same request ID. Streaming endpoints are not currently part
of the public API.

To exercise malformed JSON locally, run the API and, in another terminal:

```bash
curl -i -X POST http://127.0.0.1:8000/api/health \
  -H 'Content-Type: application/json' \
  -H 'X-Request-ID: 94801dde-c1c2-405a-894b-749617848fd9' \
  --data-binary '{"broken":'
```

The JSON integrity check runs before routing: expect 422 `request.invalid_body`
even though health normally supports GET. The response header and JSON body
must contain the supplied request ID. The terminal log shows the same ID and
`route="unmatched"`, with no submitted body. For a normal health request, expect
200 and `route="/api/health"`.
