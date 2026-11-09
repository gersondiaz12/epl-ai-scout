# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

EPL AI Scout — a Premier League scouting platform. Currently a minimal scaffold: a placeholder Next.js page and a FastAPI app with only `GET /health`. Auth, database schemas, data ingestion, ML models, the Claude API integration, and scouting features have deliberately **not** been built yet — don't add them unless asked.

## Layout

Two independent apps; they share no code or tooling.

- `apps/web` — Next.js 16 (App Router, TypeScript strict, Tailwind CSS 4, React 19). Managed as the only **npm workspace** (lockfile is the root `package-lock.json`; run `npm install` from the repo root, not inside `apps/web`). Import alias `@/*` → `apps/web/*`.
- `apps/api` — FastAPI on Python 3.12 (pinned `>=3.12,<3.13`), managed with **uv** (`pyproject.toml`, `uv.lock`, `.venv/`). `[tool.uv] package = false`: it's a plain app, not an installable package. Entry point is `app/main.py` → `app.main:app`. Not part of the npm workspace.

## Commands

From the repo root:

```bash
npm install                 # web deps (workspace)
npm run dev:web             # http://localhost:3000
npm run build:web           # production build (also type-checks)
npm run lint:web            # ESLint (next core-web-vitals + typescript configs)
npx tsc --noEmit -p apps/web  # type-check only (no npm script for it)
npm run dev:api             # cd apps/api && uv run uvicorn app.main:app --reload
```

From `apps/api`:

```bash
uv sync                                  # create/refresh .venv from uv.lock
uv run uvicorn app.main:app --reload     # http://localhost:8000/health, docs at /docs
uv add <pkg>  /  uv add --dev <pkg>      # add dependencies (updates pyproject + lock)
```

No test runner, Python linter, or Python type checker is installed yet in either app — there are no tests to run.

## Web ↔ API

Not wired up yet: no API URL config, no fetch calls, no CORS middleware. The intended pattern is Next.js server-side code (server components / route handlers) calling FastAPI via a server-only env var (e.g. `API_URL` in `apps/web/.env.local`), keeping secrets off the browser and avoiding CORS.

## Gotchas

- **Next.js 16 differs from older versions.** Per `apps/web/AGENTS.md`, read the relevant guide in `node_modules/next/dist/docs/` before writing Next.js code and heed deprecation notices. `next dev` re-creates `AGENTS.md` if it's removed.
- **Node ≥ 20.19 is required** (`engines`, `.nvmrc` = 24). Tailwind 4.3 depends on ESM-only `magic-string`, which needs native `require(esm)`. On older Node the build fails with `require() of ES Module ... magic-string ... not supported`. Turbopack spawns whichever `node` is first on PATH for loaders, so the PATH node is what matters.
- Tailwind is wired through Turbopack's CSS loader (`@tailwindcss/turbopack` in `next.config.ts`), not PostCSS. `next.config.ts` also enables `cacheComponents` and `partialPrefetching`.
- `.gitignore` ignores every `.env*` file except `.env.example`, and also ignores all `data/` and `cache/` directories and `*.csv`, `*.parquet`, `*.pkl`, `*.joblib` files repo-wide. Narrow these rules if sample data ever needs committing.
