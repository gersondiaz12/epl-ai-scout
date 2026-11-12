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
- Format every stat through `lib/format.ts`. Missing values render as an en dash, never `0`. Numeric columns are right-aligned with tabular figures (`.num`).
- Colour is never the only signal: percentile colours sit next to the number, and position colours next to the GK/DEF/MID/FWD label.
- Radars: fixed scales per position group, and always show minutes played and the comparison pool.
- Every chart gets a short plain-language explanation beside it (`.chart-block` + `.chart-note`).
- Sortable tables use `components/ui/sort-header.tsx` with `lib/sort.ts`; missing values always sort last. On phones, also offer the sort as a menu, since headers scroll out of view.
- Long tables add `.table-scroll--sticky-header` so column labels stay on screen while scrolling: from 1024px they stick under the site header, and below that the table scrolls inside a viewport-height box.
- Per-90 rates come from `lib/per90.ts`, which returns null (shown as `–`) under 270 minutes.

## Working in the repo

- Install JS dependencies from the repo root (`npm install`). `apps/web` is an npm workspace with the lockfile at the root.
- Manage Python dependencies with uv inside `apps/api` (`uv add`, `uv sync`, `uv run ...`), not pip.
- Type-check the web app with `npx tsc --noEmit -p apps/web` (there's no script for it).

## Gotchas

- **Next.js 16 has breaking changes.** Read the relevant guide in `node_modules/next/dist/docs/` before writing Next.js code (see `apps/web/AGENTS.md`).
- **Node ≥ 20.19 is required.** Tailwind 4.3 loads the ESM-only `magic-string`; older Node fails with `require() of ES Module ... magic-string ... not supported`. Turbopack uses the `node` first on PATH.
- **`.gitignore` ignores all `data/` and `cache/` directories and `*.csv`, `*.parquet`, `*.pkl` and `*.joblib` files repo-wide.** Narrow these rules before committing fixtures or sample data.
