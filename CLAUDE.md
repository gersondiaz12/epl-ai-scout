# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

EPL AI Scout is a Premier League scouting platform: `apps/web` (Next.js) and `apps/api` (FastAPI).

## Project rules

- **Deterministic Python makes every scouting judgement**: squad needs, rankings and scores. The LLM only explains decisions that have already been made; it never produces or changes them.
- **Every number shown to a user must be traceable to a database row.**
- **Ownership:** `apps/web` owns the interface, auth and shortlists. `apps/api` owns football data, models and engines.

## Working in the repo

- Install JS dependencies from the repo root (`npm install`). `apps/web` is an npm workspace with the lockfile at the root.
- Manage Python dependencies with uv inside `apps/api` (`uv add`, `uv sync`, `uv run ...`), not pip.
- Type-check the web app with `npx tsc --noEmit -p apps/web` (there's no script for it).

## Gotchas

- **Next.js 16 has breaking changes.** Read the relevant guide in `node_modules/next/dist/docs/` before writing Next.js code (see `apps/web/AGENTS.md`).
- **Node ≥ 20.19 is required.** Tailwind 4.3 loads the ESM-only `magic-string`; older Node fails with `require() of ES Module ... magic-string ... not supported`. Turbopack uses the `node` first on PATH.
- **`.gitignore` ignores all `data/` and `cache/` directories and `*.csv`, `*.parquet`, `*.pkl` and `*.joblib` files repo-wide.** Narrow these rules before committing fixtures or sample data.
