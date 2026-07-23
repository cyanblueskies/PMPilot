# Environment and commands

Windows · PowerShell — chain with `;`, not `&&`.
Python **3.11.9** (venv at `backend/venv`) · Node **24** · Docker **29.6.1**.
No local PostgreSQL install — the database runs in Docker (below).

## Commands

```powershell
# Database (from repo root) — start this first; everything else depends on it
docker compose up -d          # Postgres 17 on host port 5433
docker compose logs -f db     # watch startup
docker compose down           # stop, keep data
docker compose down -v        # stop and WIPE data (re-runs docker/init-readonly.sql)

# Frontend (from frontend/)
npm run dev            # Vite dev server
npm run build          # tsc -b && vite build
npm run lint           # oxlint — NOT ESLint

# Backend (from backend/)
.\venv\Scripts\Activate.ps1
uvicorn app.main:app --reload
pytest                                    # once installed
pytest tests/test_x.py::test_y            # single test
alembic revision --autogenerate -m "msg" ; alembic upgrade head
```

First-time setup: `Copy-Item .env.example .env`, fill in `ANTHROPIC_API_KEY`, then
`docker compose up -d`.

## Known setup traps

**`uvicorn app.main:app` fails** — `backend/app/main.py` is empty; there is no `app` object
yet. Expected at this stage.

**`alembic --autogenerate` produces an empty migration and no error** — `env.py` has
`target_metadata = None` and `alembic.ini` has the placeholder
`sqlalchemy.url = driver://user:pass@localhost/dbname`. Wire both first (`data-model.md`).

**`pytest: command not found`** — not installed. Install and add to `requirements.txt` in the
same change (`testing.md`).

**Connection refused on 5432** — the container publishes **5433** on the host, deliberately.
Use the URLs in `.env.example` verbatim.

**A new table is invisible to NL2SQL** — the read-only role's grants come from
`docker/init-readonly.sql`, which runs *once* on first volume init. `ALTER DEFAULT
PRIVILEGES` covers tables Alembic creates later; if you edit that file, the change only takes
effect after `docker compose down -v` (which destroys data).

## Dependencies

Installed backend: fastapi · uvicorn · SQLAlchemy 2.0 · alembic · pydantic · pandas 3.0 ·
numpy · psycopg2-binary · python-multipart.

Installed frontend: react 19 · react-dom · vite · typescript · oxlint. **That's all** — no
chart library, no router, no React Query.

Not installed but required by the plan: `pytest`, `httpx`, **`anthropic`** (the official SDK —
install as `anthropic`, not via an OpenAI-compatible shim), a chart library, a router,
React Query.

Rules:

- Add a dependency only when the code that needs it is being written — not in anticipation.
- **No pgvector or embedding libraries** until every Must is done (`scope.md` → FR-D4).
- Every install updates `requirements.txt` / `package.json` in the same change. `pypdf` is
  currently in the venv but not in `requirements.txt` — that drift is the failure mode.
- `requirements.txt` is currently **UTF-16 encoded**. pip tolerates it locally but it breaks
  on Linux CI and makes diffs unreadable — convert to UTF-8 when next touched.

## Scaffold status

Almost nothing is implemented. **Verify with `ls` before assuming a module exists** rather
than trusting any written inventory — a hand-maintained list of empty directories goes stale
within a week and a stale one is worse than none.

`README.md` exists but is empty. Both reference dissertations ship a live deployment URL plus
run-locally instructions in an appendix — it is a graded artefact, not decoration.

## Settled: database

**Docker Postgres 17**, defined in `docker-compose.yml`. Not SQLite — write Postgres dialect
throughout, and don't add SQLite fallbacks "for convenience in tests"; dialect divergence
showing up late is exactly what this choice avoids.

Two roles:

| Role | Used by | Grants |
|---|---|---|
| `pmpilot` | app, Alembic, tests | owner |
| `pmpilot_ro` | **NL2SQL execution only** | `SELECT` |

`pmpilot_ro` is created by `docker/init-readonly.sql` and is a required security layer
(`security.md`), not an optimisation. Never point NL2SQL at `DATABASE_URL`.

## Settled: LLM

**Claude, pinned to `claude-opus-4-8`**, read from `ANTHROPIC_MODEL_ID`. Install the official
`anthropic` Python SDK.

Two constraints that will surprise code written from memory:

- **`temperature` / `top_p` / `top_k` do not exist on this model** — sending any of them
  returns a 400. Reasoning depth is controlled by `output_config={"effort": ...}` instead.
- **Never hard-code the model string** anywhere but config. The pin is what makes the
  grounded and naive experiment arms comparable (`experiment.md`).
