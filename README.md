# PMPilot

**AI decision support for agile projects** — deterministic statistical analytics
and anomaly detection, with *grounded* LLM narration layered strictly on top of
the computed results.

University of Birmingham CS Final Year Project.

---

## What it does

Upload a Jira-style CSV/XLSX export and PMPilot:

- computes **KPIs** — velocity, cycle time, lead time, defect density, scope
  creep, workload distribution;
- detects **anomalies** — velocity drops, overdue pile-ups, blocked-task
  clusters, each with the numbers that triggered it;
- narrates the results with an LLM, and answers **natural-language questions**
  over the data via SELECT-only NL2SQL;
- generates an **executive summary + recommendations** you can export to
  Markdown or Word.

## The core idea: two tracks, one rule

The project's contribution is an architectural separation, not a wrapper around
an LLM:

- **Deterministic track** — ingestion → analytics → anomaly detection. Pure,
  unit-testable, reproducible. Produces JSON facts.
- **Generative track** — the LLM orchestrates over that JSON *only*.

**The one rule that overrides everything: the LLM never receives raw issue
tables.** It sees only the precomputed KPI/anomaly JSON, and is instructed never
to cite a number absent from that input. This is *grounded generation* — the
basis of the evaluation chapter. A deliberate **naive** prompting mode (which
*does* send raw rows) exists as the experimental baseline for measuring
hallucination; it is switchable at call time (FR-D5).

The dashboard and anomaly views are required to keep working with the LLM
entirely unavailable — the generative track is an enhancement layer, never a
dependency of the core views.

## Tech stack

| | |
|---|---|
| Backend | FastAPI · SQLAlchemy 2.0 · Alembic · pandas 3.0 · pydantic |
| Database | PostgreSQL 17 (Docker) |
| LLM | Claude (`claude-opus-4-8`), via the official `anthropic` SDK |
| NL2SQL safety | `sqlglot` (SELECT-only AST validation) · read-only DB role |
| Frontend | React 19 · Vite · TypeScript (strict) · react-router-dom · oxlint |
| Charts | Hand-built inline SVG (no chart library) |

## Prerequisites

- Python **3.11**
- Node **24**
- Docker (for PostgreSQL — there is no local Postgres install)

## Quick start

The app runs as three processes. Open three terminals.

**1 — Database** (repo root — `docker-compose.yml` lives here):

```powershell
docker compose up -d          # PostgreSQL 17 on host port 5433
```

**2 — Backend** (`backend/`):

```powershell
Copy-Item ..\.env.example ..\.env   # first time only; then fill in ANTHROPIC_API_KEY
.\venv\Scripts\Activate.ps1
alembic upgrade head                # create the schema (first time)
uvicorn app.main:app --port 8000
```

API docs: <http://127.0.0.1:8000/docs>

**3 — Frontend** (`frontend/`):

```powershell
npm install                   # first time only
npm run dev
```

Open **<http://localhost:5173>**.

Try it with `data/sample/demo.csv`, or generate your own dataset (below).

> The generative track (summaries, recommendations, NL2SQL) needs a real
> `ANTHROPIC_API_KEY` in `.env`. Without one, the dashboard, charts, and anomaly
> views all still work — the LLM features degrade gracefully with a clear
> message.

## Gotchas

These trip people up; all are deliberate.

- **Use `localhost:5173`, not `127.0.0.1:5173`** — the Vite dev server binds the
  IPv6 loopback. The backend is the opposite: reach it at `127.0.0.1:8000`.
- **The database is on host port `5433`, not `5432`** — chosen so it never
  shadows a locally-installed Postgres. Use the URLs in `.env.example` verbatim.
- **Don't run the backend with `--reload`** — on some Windows setups it detects
  changes but never loads the new code. Restart `uvicorn` after backend edits.
- **`pytest` truncates the database.** The test suite runs against the same
  Postgres and wipes the tables between tests. Don't run it while you have data
  loaded in the UI you want to keep.
- The Windows launcher shims in `backend/venv/Scripts/` bake in an absolute path
  at creation time; if the repo is moved or renamed, run commands as
  `python -m uvicorn …` / `python -m pytest`, or recreate the venv.

## Testing

```powershell
cd backend
.\venv\Scripts\Activate.ps1
pytest                                          # all
pytest tests/test_kpi.py -q                     # one file
```

The deterministic track is covered directly (every KPI with hand-checked values,
anomaly threshold boundaries, ingestion edge cases). The generative track is
tested at the prompt-construction level — that grounded mode's prompt contains
no raw issue rows — never with live LLM calls; model responses are scored
separately from the persisted `query_logs` rows.

## Synthetic data

Real enterprise Jira data is deliberately not used. The FR-A4 generator emits a
fixed-seed dataset plus a **separate** machine-readable ground-truth manifest
(which sprints/issues carry which injected anomaly), which is the source of truth
for detection-F1 evaluation:

```powershell
python data/scripts/generate_dataset.py --name demo --out data/sample
# -> demo.csv  +  demo.truth.json
```

## Project layout

```
backend/
  app/
    api/        thin routes — validate, call a service, serialise
    services/   ingestion · analytics · anomaly · llm · nl2sql · export
    models/     SQLAlchemy ORM
    schemas/    Pydantic API contracts
    core/       config
  alembic/      migrations
  tests/
frontend/
  src/
    api/        typed client + backend contract mirror
    components/ charts, panels, primitives
    pages/      projects list · project dashboard
docker/         init-readonly.sql (creates the NL2SQL read-only role)
data/           sample dataset + synthetic-data generator
docs/           PRD and technical requirements (authoritative, Chinese)
```

Architecture, scope, data-model, and coding rules live under `.claude/rules/`.

## Status

The full core loop is implemented and runs locally: upload → KPIs → anomalies →
grounded summary → NL2SQL → report export. Public deployment is pending.
