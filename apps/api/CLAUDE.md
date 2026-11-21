# apps/api: data pipeline conventions

## Sources (approved; check terms before adding another)

- **FPL** (bootstrap-static, element-summary, fixtures): the roster, season stats, advanced stats (xG, xA, defensive counts) and past seasons. Used with the Premier League's written permission (confirmed 2026-11-17); FPL's own T&Cs (clause 28) otherwise forbid automated extraction. Add any conditions of that permission here as rules.
- **Transfermarkt**, used with Transfermarkt's written permission (confirmed 2026-11-17); its terms otherwise forbid scraping and AI use:
  - **Bulk:** dcaribou/transfermarkt-datasets (CC0-1.0), `app.ingest.transfermarkt`. Frozen: values end 2026-06-12, and contracts and clubs are a July 2026 snapshot.
  - **Live:** the self-hosted felipeall/transfermarkt-api, `app.ingest.transfermarkt_api`.
    - Local hosts only (`TRANSFERMARKT_API_URL`, default `http://127.0.0.1:8100`).
    - Runs as a scheduled job only: never import it from a router or call the API from a web request (`test_no_web_route_imports_the_job` checks).
- Market values are EUR as published, never converted or estimated. Show a value's date wherever it's shown.
- **Not available from any allowed source:** progressive passes and carries, pressures, duels, aerials, shot-stopping quality (post-shot xG). Don't add a source for them without checking its terms.

## Fetching and raw cache

- Every response is saved untouched under `data/raw/<source>/<date>/` before parsing (via a `.part` file, never half-written). A re-run the same day reuses the cache.
- **Throttling:**
  - FPL: at most 5 requests at a time.
  - Transfermarkt live: one request at a time, at least 5 s apart (2 s floor). It backs off on 429/5xx and stops the run if the upstream stays blocked, loading nothing.
- **Versions:** each bulk download or live run is a `source_snapshots` row (file SHA-256s, `data_through`). Every value and contract row cites its snapshot.
- Tests use fixtures or a mock transport, never a live source.

## Storing

- Every schema change is a reviewed Alembic migration, and `uv run alembic check` must report no drift.
- **Seasons** are keyed by label (`"2026-27"`), and exactly one is current. There's one stats row per (player, season, club), so a mid-season transfer gives two rows.
- **Past seasons** live in `player_season_totals` (`app.ingest.fpl_history`): no dates, never current, and no club split. FPL's history covers only players still in the game.
- **Totals, not rates.** Per-90 values and percentiles are computed on read.
  - Exception: a source's snapshot figure that can't be rebuilt from totals (FPL `form`). Store it as given, on the current-club row, with `ingested_at`.
- A field the source didn't track that season is null, never 0.
- **External ids** are `(source, external_id)` rows, and only ids stable across seasons (FPL `code`, never its per-season `id`). A new source adds rows, not columns.

## Idempotent upserts

- Upserts use `on_conflict_do_update` with a `WHERE` clause on `is_distinct_from`, so a row is rewritten only when a data value changes.
  - Provenance (`snapshot_id`, `ingested_at`) moves only with a real change.
  - Count written rows with `RETURNING`, never `rowcount`.
  - Batch at most 5,000 rows per insert (Postgres has a 65,535-parameter limit).
- Re-running a job on the same input writes nothing. Check this with a test.
- The FPL ingest rolls back unless every player's rows match FPL's season totals.
- The frozen bulk load never overwrites a value the live API wrote for the same date, because Transfermarkt revises values.
- Never drop a record silently: count every skip by reason and log examples.

## Player identity (`app/identity/`)

- Players are created only from FPL, by `code`. Every other source links to them through one deterministic matcher, never ML. The first decisive stage wins:
  1. **Manual decisions**;
  2. **stored links**, kept and never changed automatically; contradicting evidence is queued as `conflict_with_existing_link`;
  3. **rules**, with the same birth date unless stated:
     - R1: same words in any order;
     - R2: one name's words within the other's, with given names agreeing;
     - R3: the reviewed alias table;
     - R4: no birth date on one side, but the same club this season (any of the player's clubs);
  4. **fuzzy:** word-aligned score ≥ 0.75, at least 2 words on each side, and 0.10 ahead of the next candidate.
- **Where results go:**
  - `player_source_ids.method` records how each link was made;
  - records that couldn't be matched go to `unmatched_records`, with candidates and a reason;
  - each run is a `match_runs` row with its settings and counts.
- The threshold was measured on real pairs: twins born the same day must stay below it. Re-measure before changing it (`tests/test_identity_stages.py`).
- Add to `aliases.py` only from a real pair you've checked.
- Match rate: `npm run api:identity:report`.

## Manual overrides always win

- Decisions live in `player_match_decisions` (`link`, `reject`, `no_match`) and are made with `npm run api:identity:resolve -- ...`.
  - They're append-only: a new decision supersedes the old one, which is kept, never deleted.
  - Every decision needs a reason.
- The matcher applies decisions first and only reads them, so no run ever overwrites a manual decision or changes a `manual` link.
- Removing or moving a link deletes the data loaded through it. A new manual link gets its data on the source's next run.

## Gotchas

- Settings come from `app/config.py` (pydantic-settings), which loads `apps/api/.env`. Claude can't read or write `.env` files (a deny rule), so never open them.
  - Check the connection with `make_url(...).render_as_string(hide_password=True)`.
  - Ask the user to edit `.env`.
- `position` is a reserved word in Postgres type names, so the enum type is `player_position`.
- Tests run against the `epl_scout_test` database, with the schema built by the real migrations (`npm run api:test`).
