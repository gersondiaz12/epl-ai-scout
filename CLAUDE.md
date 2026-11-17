# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

EPL AI Scout is a Premier League scouting platform: `apps/web` (Next.js) and `apps/api` (FastAPI).

## Project rules

- **Deterministic Python makes every scouting judgement**: squad needs, rankings and scores. The LLM only explains decisions that have already been made; it never produces or changes them.
- **Every number shown to a user must be traceable to a database row.**
- **Ownership:** `apps/web` owns the interface, auth and shortlists. `apps/api` owns football data, models and engines.

## Design system (apps/web)

- Tokens live in `apps/web/styles/tokens.css` and component classes in `apps/web/styles/components.css`. Use the token utilities (`bg-surface`, `text-fg-muted`, `border-border`, `pos-*`, `pct-*`) instead of raw Tailwind palette colours.
- No club crests, league logos or player photos anywhere.
- Format every stat through `lib/format.ts`. Values the data source doesn't provide show "Not yet available" (`components/ui/not-available.tsx`), never an estimate. An en dash means not applicable (e.g. per-90 under 270 minutes), never `0`. Numeric columns are right-aligned with tabular figures (`.num`).
- Colour is never the only signal: percentile colours sit next to the number, and position colours next to the GK/DEF/MID/FWD label.
- Radars: fixed scales per position group, and always show minutes played and the comparison pool.
- Every chart gets a short plain-language explanation beside it (`.chart-block` + `.chart-note`).
- Sortable tables use `components/ui/sort-header.tsx` with `lib/sort.ts`; missing values always sort last. On phones, also offer the sort as a menu, since headers scroll out of view.
- Long tables add `.table-scroll--sticky-header` so column labels stay on screen while scrolling: from 1024px they stick under the site header, and below that the table scrolls inside a viewport-height box.
- Percentiles compare a player only with the same position (at least 270 minutes), and always state the pool size and the player's minutes.
- Reserve space for unbuilt features with `components/ui/empty-slot.tsx` (dashed panel, "Not built yet", never any numbers).
- Per-90 values and percentiles come from the API (null, shown as `–`, under 270 minutes). The web app formats them; it never computes them.

## Data (apps/api)

- **Table ownership:** football tables belong to apps/api (SQLAlchemy 2 models, Alembic migrations). App tables (users, shortlists) will belong to apps/web, managed with Drizzle. Neither side migrates the other's tables, and there are no cross-app foreign keys. Every schema change is a reviewed Alembic migration, and `uv run alembic check` must report no drift.
- **Seasons** are keyed by label (`"2026-27"`). Exactly one is marked current, and the API defaults to it when no `season` is given. Season-scoped data hangs off the season: one stats row per (player, season, club), so a mid-season transfer gives two rows.
- **Source ids:** players and clubs carry external ids as `(source, external_id)` rows, one per source. Store only ids that are stable across seasons (FPL's `code`, never its per-season `id`). A new source adds rows, not columns.
- Store totals, not rates. Per-90 values and percentiles are computed on read. The exception is a source's own snapshot figure that can't be rebuilt from totals, such as FPL `form` (`player_season_stats.form`): store it as given, on the current-club row only, and say when it was taken (`ingested_at`). Rankings built on it (`GET /in-form`) are ordered in the API, never in the web app.
- The ingest rolls back unless every player's rows match the source's season totals.
- apps/web reads data only through `lib/api.ts`, inside `<Suspense>` after `await connection()`, so `next build` never needs the API. Keep `lib/types.ts` in step with `app/schemas.py`.

## Working in the repo

- Install JS dependencies from the repo root (`npm install`). `apps/web` is an npm workspace with the lockfile at the root.
- Manage Python dependencies with uv inside `apps/api` (`uv add`, `uv sync`, `uv run ...`), not pip.
- Type-check the web app with `npx tsc --noEmit -p apps/web` (there's no script for it).
- Local data: `npm run db:up`, `npm run api:migrate`, `npm run api:ingest`. API checks: `npm run api:test` (uses the `epl_scout_test` database) and `npm run api:lint`.

## Gotchas

- **Next.js 16 has breaking changes.** Read the relevant guide in `node_modules/next/dist/docs/` before writing Next.js code (see `apps/web/AGENTS.md`).
- **Node ≥ 20.19 is required.** Tailwind 4.3 loads the ESM-only `magic-string`; older Node fails with `require() of ES Module ... magic-string ... not supported`. Turbopack uses the `node` first on PATH.
- **`position` is a reserved word in Postgres type names**, so the enum type is `player_position` (the column is still `position`).
- **The API's settings come from `app/config.py` (pydantic-settings), which loads `apps/api/.env`.** Claude can't read or write `.env` files (deny rule, which also blocks `.env.example`), so never open them. Check the connection through `settings` with `make_url(...).render_as_string(hide_password=True)`, and ask the user to edit `.env`.
- **`.gitignore` ignores all `data/` and `cache/` directories and `*.csv`, `*.parquet`, `*.pkl` and `*.joblib` files repo-wide.** Narrow these rules before committing fixtures or sample data.
