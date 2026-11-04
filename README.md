# AccessFlow

Web platform for employee onboarding and offboarding driven by configurable
business processes.

## Status

Rebuild in progress. The backend API, the local infrastructure and the
development user script are described below; the frontend is a minimal
application without screens yet.

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

| Service    | Address                 | Notes                                                           |
|------------|-------------------------|-----------------------------------------------------------------|
| PostgreSQL | `127.0.0.1:5432`        | Databases `accessflow` and `keycloak`                           |
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
| `make logs`          | Follow the logs                                         |
| `make migrate`       | Apply the database migrations as `accessflow_owner`     |
| `make web`           | Start the frontend dev server                           |
| `make check`         | All backend and frontend checks                         |
| `make check-fast`    | Formatting, lint, types and unused-code checks          |
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

### Run

The API reads its settings from `ACCESSFLOW_*` environment variables: the
`ACCESSFLOW_DATABASE_*` connection settings and the `ACCESSFLOW_AUTH_*` access
token settings listed in `.env.example` (migrations need only the database
ones). The database port defaults to 5432 and the token audience
`ACCESSFLOW_AUTH_AUDIENCE` to `accessflow-api`; every other variable is
required and must not be empty, and without it the application refuses to
start. The API connects as `accessflow_app`, which can read and change data but
not the schema.

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
- a request that needs the keys while they are being downloaded waits for that
  download, at most 5 seconds, and then gets 503; a failed download is not
  repeated for 10 seconds, and a request that needs the keys in that time gets
  503 at once.

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
format check), mypy in strict mode, import-linter and pytest. Warnings raised
during tests are treated as errors.

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
`request.too_large` whatever its media type; the limit is checked on the
declared `Content-Length` and again while the body is read, before routing.
JSON bodies are checked before routing when the media type is
`application/json`, `application/*+json` or absent. Bodies of other media types
are left to endpoint validation.

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
line where it was raised). Uvicorn's default access logger is disabled by the
application; keep `--no-access-log` in launch commands as well. Server
exception logs omit tracebacks and preserve the request ID for failures after a
response starts.
Do not enable a second HTTP access logger with raw URLs or body logging.
These operational logs are not a business audit trail.

If a streamed response has already started, HTTP cannot replace its status or
body with a 500 problem. The stream fails, and its original status is logged
at ERROR with the same request ID. Streaming endpoints are not currently part
of the public API.

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
pnpm exec playwright install chromium
```

The last command downloads the Chromium build that matches the installed
Playwright version; repeat it after Playwright is updated.

pnpm switches to the version from `packageManager` by itself. The install fails
under a Node.js version outside `engines` in `package.json`; run `nvm use` in
every new terminal before working on the frontend or running `make check`.

### Run

```bash
make web
```

The dev server runs at `http://localhost:5173` and forwards requests under
`/api` to the API at `http://127.0.0.1:8000`, so the browser talks to a single
origin. Start the API as described in [Backend](#run) to work with data.

### Styles

Components are styled with CSS Modules. Design values are CSS custom properties
in `frontend/src/shared/styles/tokens.css`: spacing, radii, sizes, text styles,
shadows, layers and motion, and colors in two layers, a palette and semantic
tokens on top of it (`--bg-page`, `--text-primary`). Components use the
semantic colors, never the palette. `base.css` next to it holds the reset, the
base typography, the focus ring and the rule that turns off animations and
transitions when the system asks for reduced motion.

Stylelint keeps values in the tokens. Outside `tokens.css` it rejects hex and
named colors, color functions and gradients, any unit other than `%`, `fr` and
`deg`, font families, sizes, line heights and z-index values that are not
tokens, and font weights other than 400 and 600. It also rejects
`backdrop-filter`, uppercase text and transitions or keyframes of width,
height, margin and padding. Media queries may use only the two breakpoints,
767px and 1360px.

The only typeface is Golos Text, one variable font file in
`frontend/src/shared/styles/fonts/` with its SIL Open Font License next to it;
nothing is loaded from external servers. The icons and the link preview image
are in `frontend/public/`.

`tokens.test.ts` checks the contrast of the color pairs the interface uses
(4.5:1 for text, 3:1 for borders, focus rings and the logo mark), that the
palette has no pure black or white, and that the font stack has no banned
typeface and starts with the bundled one. `index.html.test.ts` checks the page
title, the meta tags, the icons and the Open Graph tags.

### Checks

`make check` runs the frontend checks after the backend ones: it installs
exactly the versions from `pnpm-lock.yaml` and fails if the lockfile does not
match `package.json`, checks formatting with Prettier, lints the code with
ESLint and the styles with Stylelint, type-checks the code with the TypeScript
compiler in strict mode, checks for unused files, exports and dependencies with
Knip, runs the tests and builds the production bundle into
`frontend/dist`. ESLint fails on warnings as well as errors.

To fix formatting, run `pnpm format` in `frontend/`.

ESLint uses the type-aware strict rules of typescript-eslint, the React Hooks
and React Compiler rules, accessibility rules for JSX and the TanStack Query and
Router rules. It also enforces the layers of `frontend/src`: `app` may import
`pages`, `features` and `shared`, `pages` may import `features` and `shared`,
a feature may import `shared` but not another feature, and `shared` imports
nothing above it. Every file under `src` must belong to one of these layers.

Tests run on [Vitest](https://vitest.dev/) in two projects, chosen by the file
extension. `*.test.ts` files form the `unit` project and run in Node.js; they
cover code without a user interface. `*.test.tsx` files form the `browser`
project and run in headless Chromium through Playwright, because focus and
keyboard behave there as in a real browser. Tests live next to the code they
cover. To run one project, use `pnpm test --project unit` or
`pnpm test --project browser` in `frontend/`. Screenshots of failed browser
tests are saved to `frontend/.vitest/attachments`.

## Continuous integration

The CI workflow runs on every push to `main` and can also be started manually
from the repository's Actions tab. Backend and frontend checks run in separate
jobs on Ubuntu 24.04:

- Backend runs `make backend-check` and `make test-keycloak`. Testcontainers
  uses the runner's Docker daemon for disposable PostgreSQL and Keycloak
  containers; no development services or environment file are needed.
- Frontend runs `make frontend-check`, including Knip and browser tests.
  Chromium and its system dependencies are installed before the checks.

Node.js comes from `.nvmrc`, pnpm from `frontend/package.json`, and Python
from `backend/.python-version`; uv is pinned in the workflow. Dependency caches
use the lockfiles, and the browser cache uses the frontend lockfile. Actions
are pinned to full commit hashes. A newer run on the same branch cancels an
older run of this workflow.

### Security checks

The Security workflow runs every Monday at 04:17 UTC, on pushes to `main`
that change a dependency lockfile or a workflow, and manually from Actions.
Its jobs run independently:

- OSV-Scanner checks `backend/uv.lock` and `frontend/pnpm-lock.yaml` for known
  vulnerabilities. Package names and versions are queried against the OSV
  database.
- Gitleaks scans the Git history of the checked-out branch with the default
  rules; detected secret values are fully redacted in the output.
- Zizmor checks the workflow files and reports findings as GitHub annotations.

The scanner versions are pinned, and the downloaded OSV-Scanner and Gitleaks
binaries are verified against fixed SHA256 checksums before execution. Any
finding fails its job.

Dependabot alerts are enabled in the repository settings and complement the
scheduled scan; dependency updates remain manual.

### Local Git hooks

Lefthook is pinned in `frontend/package.json`. Gitleaks must be available on
`PATH`; CI uses version 8.30.1. On macOS, install it with
`brew install gitleaks`; other platforms can use the
[official releases](https://github.com/gitleaks/gitleaks/releases).

After cloning or pulling this configuration, install the hooks once from the
repository root:

```bash
nvm use
pnpm --dir frontend install --frozen-lockfile
pnpm --dir frontend hooks install
```

The last command writes the local Git hooks; those files are not committed.
Dependency installation and manual hook runs do not install hooks automatically.
Run Git from a terminal where Node.js, pnpm, uv and Gitleaks are available.

Before a commit, Ruff checks staged Python files; Prettier, ESLint and
Stylelint check staged frontend files, and Gitleaks scans the staged diff.
Checks report errors without fixing files or automatically staging fixes.

Before a push, `make check-fast` checks lockfile consistency, formatting, lint,
types, module boundaries and unused code across both projects. It does not
run tests or build the frontend, and needs no Docker daemon. Run `make check`
before committing and `make test-keycloak` before pushing.

To run the hooks manually from the repository root:

```bash
pnpm --dir frontend hooks run pre-commit
pnpm --dir frontend hooks run pre-push
```
