# EPL AI Scout

A Premier League scouting platform.

## Structure

```
apps/
  web/   Next.js (TypeScript, App Router, Tailwind CSS): interface, auth, shortlists
  api/   FastAPI (Python 3.12, uv): football data, models, engines
docker-compose.yml   Postgres 17 + pgvector for apps/api
```

## Getting started

Prerequisites: Node.js 20.19+ (24 LTS recommended, see `.nvmrc`), npm, Python 3.12, [uv](https://docs.astral.sh/uv/), Docker.

```bash
npm install              # web dependencies (npm workspaces)
(cd apps/api && uv sync) # api dependencies

npm run db:up            # Postgres + pgvector on localhost:5433
npm run api:migrate      # create the football tables
npm run api:ingest       # load the current season from Fantasy Premier League (~20 s)

npm run dev:api          # http://localhost:8000 (docs at /docs)
npm run dev:web          # http://localhost:3000
```

Run `npm run api:ingest` again to refresh the data. Responses are cached per day under `apps/api/data/raw/fpl/`; add `-- --refresh` to fetch again on the same day.

## Scripts

Run from the repo root.

| Script | Runs | What it does |
|---|---|---|
| `dev:web` | `next dev` in `apps/web` | Starts the web app with hot reload on port 3000. |
| `build:web` | `next build` in `apps/web` | Production build. Doesn't need the API running. |
| `lint:web` | `eslint` in `apps/web` | Lints the web app. |
| `dev:api` | `uv run uvicorn app.main:app --reload` | Starts the API with auto-reload on port 8000. |
| `db:up` | `docker compose up -d --wait db` | Starts Postgres 17 with pgvector in Docker on port 5433, and waits until it accepts connections. Data persists in a Docker volume. The first start also creates the empty `epl_scout_test` database for tests. |
| `db:down` | `docker compose stop db` | Stops the database container and keeps its data. |
| `api:migrate` | `uv run alembic upgrade head` | Applies any database migrations not yet run (it creates the tables on first run). Safe to repeat. |
| `api:ingest` | `uv run python -m app.ingest.fpl` | Downloads the current season from Fantasy Premier League and reloads the season's clubs, players and stats in one transaction. It rolls back unless every player's stored rows match FPL's season totals. |
| `api:test` | `uv run pytest` | Runs the API tests against `epl_scout_test`, never the main database. |
| `api:lint` | `ruff check` and `ruff format --check` | Lints and checks formatting of the API code. |

## Checks

```bash
npm run api:test    # pytest, against the epl_scout_test database
npm run api:lint    # ruff
npm run lint:web
npm run build:web   # doesn't need the API running
```

## Environment variables

Both apps work locally with no `.env` file. Override as needed:

| App | Variable | Default |
|---|---|---|
| api | `DATABASE_URL` | `postgresql+psycopg://scout:scout@localhost:5433/epl_scout` |
| api | `TEST_DATABASE_URL` | the same server, database `epl_scout_test` |
| web | `API_URL` | `http://localhost:8000` |

Keep secrets in `.env` files. Every `.env*` file is gitignored.
