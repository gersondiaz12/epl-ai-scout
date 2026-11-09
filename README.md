# EPL AI Scout

A Premier League scouting platform. Early scaffold — no features yet.

## Structure

```
apps/
  web/   Next.js (TypeScript, App Router, Tailwind CSS)
  api/   FastAPI (Python 3.12, managed with uv)
```

## Getting started

Prerequisites: Node.js 20.19+ (24 LTS recommended, see `.nvmrc`), npm, Python 3.12, [uv](https://docs.astral.sh/uv/).

```bash
# install web dependencies (npm workspaces)
npm install

# web — http://localhost:3000
npm run dev:web

# api — http://localhost:8000/health
cd apps/api
uv sync
uv run uvicorn app.main:app --reload
```

## Environment variables

Keep secrets in `.env` files. Every `.env*` file is gitignored; commit only `.env.example` templates.
