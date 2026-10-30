# AccessFlow

Web platform for employee onboarding and offboarding driven by configurable business processes.

## Status

Rebuild in progress. The backend API, the local infrastructure and the development user script are described below; the frontend is a minimal application without screens yet.

## Local infrastructure

PostgreSQL and Keycloak run in Docker Compose. All ports are bound to
`127.0.0.1`, so the services are reachable only from your machine.

### Requirements

- Docker with Compose v2 (`docker compose version`)
- GNU Make
- [uv](https://docs.astral.sh/uv/) for the backend
- Node.js 26 and pnpm 12 for the frontend (see [Frontend](#frontend))

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

| Command              | What it does                                            |
|----------------------|---------------------------------------------------------|
| `make up`            | Start the services and wait until they are healthy      |
| `make down`          | Stop and remove the containers; the data volume is kept |
| `make ps`            | Show the state of the services                          |
| `make logs`          | Follow the logs (stop with Ctrl+C)                      |
| `make migrate`       | Apply the database migrations as `accessflow_owner`     |
| `make web`           | Start the frontend dev server                           |
| `make check`         | All backend and frontend checks                         |
| `make test-keycloak` | Backend tests against a disposable Keycloak             |

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

The API reads its settings from `ACCESSFLOW_*` environment variables:
the `ACCESSFLOW_DATABASE_*` connection settings and the `ACCESSFLOW_AUTH_*` access
token settings listed in `.env.example` (migrations need only the database ones). The database port defaults to 5432 and
the token audience `ACCESSFLOW_AUTH_AUDIENCE` to `accessflow-api`; every other
variable is required and must not be empty, and without it the application
refuses to start. The API
connects as `accessflow_app`, which can read and change data but not the schema.

The application itself does not read `.env`; `uv run --env-file` loads it into
the process environment. Start the dev stack (`make up`) first, then:

```bash
cd backend
uv run --frozen --env-file ../.env uvicorn accessflow.app:create_app \
  --factory --host 127.0.0.1 --port 8000 --no-access-log
```

Check that the process is alive and that it reaches the database:

```bash
curl -i http://127.0.0.1:8000/api/health
curl -i http://127.0.0.1:8000/api/ready
```

`/api/health` answers `200 OK` with `{"status":"ok"}` while the process runs.
`/api/ready` answers the same only when the database is reachable, and
`503` with the code `service.unavailable` otherwise, including when the database
does not answer within 3 seconds.

The API bounds its waits for the database: a connection attempt and a wait for a
free pooled connection each give up after 5 seconds, and PostgreSQL cancels a
statement after 10 seconds, a lock wait after 5 and an idle open transaction
after 30. TCP keepalives and a 30-second user timeout detect a connection whose
peer has vanished. Migrations connect without the statement and lock limits.

### Authentication

Every endpoint under `/api` except `/api/health` and `/api/ready` requires a
Keycloak access token in the `Authorization: Bearer <token>` header. The API
verifies the token against the realm's public signing keys
(`ACCESSFLOW_AUTH_JWKS_URL`):

- only RS256 is accepted; the algorithm and the key ID are checked before any
  key is loaded;
- `iss` must equal `ACCESSFLOW_AUTH_ISSUER` exactly, `aud` must include
  `accessflow-api`, and `exp`, `iat`, `iss`, `aud` and `sub` are required;
  clocks may differ by up to 30 seconds;
- the keys are cached for 5 minutes; a token with an unknown key ID reloads
  them at most once every 30 seconds; each network operation of a download
  times out after 5 seconds;
- a failed download is not repeated for 10 seconds, and requests that need the
  keys while a download is running get 503 at once instead of waiting.

Roles come from `realm_access.roles` and must match exactly (`HR`, not `hr`).

| Status | Code                        | When                                            |
|--------|-----------------------------|-------------------------------------------------|
| 401    | `auth.invalid_token`        | No token, or the token is invalid or expired    |
| 403    | `auth.forbidden`            | Valid token, but the required role is missing   |
| 503    | `auth.provider_unavailable` | The signing keys cannot be loaded from Keycloak |

`GET /api/me` answers any signed-in user, with or without roles, so the
interface can decide what to show:

```json
{"displayName": "Анна Смирнова", "roles": ["HR", "default-roles-accessflow"]}
```

The name is the `name` claim, or `preferred_username` when `name` is empty; a
token with neither is rejected with 401.

### Development users

The realm file has no users. Create them in the dev Keycloak while the stack
is running:

```bash
cd backend
uv run --frozen --env-file ../.env python scripts/create_dev_user.py \
  --username a.smirnova --email a.smirnova@example.test \
  --first-name Анна --last-name Смирнова --hr
```

The script signs in to the Admin API as `admin` with `KEYCLOAK_ADMIN_PASSWORD`
and asks for the new user's password twice. The password is never printed or
stored anywhere except Keycloak. Keycloak checks it against the realm policy
(at least 12 characters) and creates nothing when it fails; an existing
username or email is rejected with 409. Without `--hr` the script assigns no
role; the user still has the realm's default roles, which `/api/me` lists, and
endpoints for HR return 403. If the user is created but the role cannot be
assigned, the script prints the user's ID and stops: assign the role in the
admin console or delete the user and run the script again.

To check the password, sign in to the account console at
`http://localhost:8081/realms/accessflow/account`.

### Migrations

The schema is changed only by Alembic migrations in `backend/migrations/`.
They run as `accessflow_owner`, the owner of the `accessflow` database. Tables
it creates are granted to `accessflow_app` for data access through default
privileges; tables created by any other role would stay out of the API's reach.
Every run also removes the API role's access to `alembic_version`, so the
migration state cannot be changed through the API; an existing database gets
this with the next `make migrate`.

Apply the migrations to the dev database (the stack must be running):

```bash
make migrate
```

Create a new migration from the model changes, then review it before use:

```bash
cd backend
uv run --frozen --env-file ../.env sh -c \
  'ACCESSFLOW_DATABASE_USER=accessflow_owner ACCESSFLOW_DATABASE_PASSWORD="$ACCESSFLOW_OWNER_PASSWORD" alembic revision --autogenerate -m "describe the change"'
```

New files are formatted with Ruff automatically. Constraint and index names
follow the naming convention in `accessflow/core/db.py`.

### Checks

Run from the repository root:

```bash
make check
```

It checks that `uv.lock` matches `pyproject.toml`, then runs Ruff (lint and
format check), mypy in strict mode, import-linter and pytest. Warnings raised during tests are treated as errors.

import-linter enforces the module boundaries declared in `backend/pyproject.toml`:
`app` may import `modules` and `core`, `modules` may import `core`, never the
other way round; a module uses another one only through its `service` and
`schemas`; services do not import FastAPI or Starlette, and routers do not
import SQLAlchemy directly.

Database tests need a running Docker daemon. They start a disposable
PostgreSQL 18 container on a random port, initialized by the same scripts as
the dev stack, and remove it afterwards; the dev stack and its data are never
used. Migrations run as `accessflow_owner`, the tests connect as
`accessflow_app`, and every test runs in a transaction that is rolled back.
Migration tests (pytest-alembic) use a separate empty database in the same
container.

`make check` leaves out the tests marked `keycloak`; run them with:

```bash
make test-keycloak
```

They start a disposable Keycloak 26.8 container on a random port that imports
`infra/keycloak/realm-accessflow.json`, create test users with random
passwords through the Admin API and call the API with the access tokens
Keycloak issues to them. Signing in with a username and password is a test-only
addition made inside that container: it is enabled for `accessflow-web`, and a
second client, `accessflow-tests`, issues tokens without the `accessflow-api`
audience. The realm file itself has neither users nor password sign-in.

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
numbers (`NaN`, `Infinity` and values such as `1e400` that overflow to infinity)
return 422 `request.invalid_body`. A request body larger than 1 MiB returns 413
`request.too_large`; the limit is checked on the declared `Content-Length` and
again while the body is read. JSON bodies are checked before
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

## Frontend

The web client is a React and TypeScript application in `frontend/`, built with
[Vite](https://vite.dev/) and managed by [pnpm](https://pnpm.io/). The Node.js
version is pinned in `.nvmrc`, the pnpm version in the `packageManager` field of
`frontend/package.json`, and the dependency versions in `frontend/pnpm-lock.yaml`.

### Setup

Node.js 26 no longer ships Corepack, so pnpm is installed once with npm. With
[nvm](https://github.com/nvm-sh/nvm), from the repository root:

```bash
nvm install
npm install -g pnpm@12
cd frontend
pnpm install --frozen-lockfile
```

pnpm switches to the version from `packageManager` by itself. The install fails
under a Node.js version outside `engines` in `package.json`; run `nvm use` in
every new terminal before working on the frontend or running `make check`.

### Run

```bash
make web
```

Vite serves the application at `http://localhost:5173` and reloads it on every
change.

### Checks

`make check` runs the frontend checks after the backend ones: it installs
exactly the versions from `pnpm-lock.yaml` and fails if the lockfile does not
match `package.json`, checks formatting with Prettier, lints the code with
ESLint and the styles with Stylelint, type-checks the code with the TypeScript
compiler in strict mode and builds the production bundle into `frontend/dist`.
ESLint fails on warnings as well as errors.

To fix formatting, run `pnpm format` in `frontend/`.

ESLint uses the type-aware strict rules of typescript-eslint, the React Hooks
and React Compiler rules, accessibility rules for JSX and the TanStack Query and
Router rules. It also enforces the layers of `frontend/src`: `app` may import
`pages`, `features` and `shared`, `pages` may import `features` and `shared`,
a feature may import `shared` but not another feature, and `shared` imports
nothing above it. Every file under `src` must belong to one of these layers.
