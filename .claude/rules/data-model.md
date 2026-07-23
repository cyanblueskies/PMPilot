# Data model and API

Schema: `docs/Project_Requirements.md` §5.3. API list: §5.5.

## Core tables

`projects` · `sprints` · `issues` (the fact table) · `kpi_snapshots` · `anomalies` ·
`query_logs` · `reports`

### `query_logs` and `kpi_snapshots` are instrumentation, not caches

They feed the quantitative evaluation in §8. **Preserve their write paths** — never
"optimise" them away, never make them conditional on a debug flag.

`query_logs` has mandatory fields (`raw_prompt`, `raw_response`, `model_id`,
`prompting_strategy`, `grounding_payload`, `latency_ms`) — see `experiment.md` for the full
table and why `grounding_payload` is load-bearing.

`anomalies` rows must be comparable against the FR-A4 ground-truth manifest, so store the
anomaly **type** and the **sprint/issue it attaches to** as structured columns, not prose.

## Input schema (Jira-style CSV/XLSX)

Issue Key · Issue Type · Status · Assignee · Reporter · Priority · Story Points · Sprint ·
Created Date · Resolved Date · Due Date · Labels · Epic Link · Original Estimate · Time
Spent · Description · Comments

Design for **500–5,000 issues** and **5–20 sprints** per project. KPI + anomaly computation
is budgeted at **<5s** at that scale (`architecture.md`).

Notes that bite during ingestion:

- Column names vary between Jira exports — hence field mapping (FR-A2/A3). Don't hard-code
  header strings in the analytics layer; map to an internal schema at the boundary.
- All three date columns arrive with timezone offsets → parse to UTC-aware
  (`code-style.md`).
- `Story Points` is frequently blank. Blank ≠ 0 for velocity; decide and document the rule.
- `Description` and `Comments` are free text. They are the *only* fields RAG would use, and
  RAG is deferred — the deterministic track must not depend on them.

## Alembic

`alembic/env.py` currently has `target_metadata = None` and `alembic.ini` has the placeholder
URL. **Autogenerate silently emits empty migrations until both point at the real ORM `Base`
and a live database** — no error, just an empty file. Wire both before the first migration.

```powershell
alembic revision --autogenerate -m "msg" ; alembic upgrade head
```

Every schema change ships with a migration in the same commit.

## API surface (planned, `/api` prefix)

| Method | Path |
|---|---|
| POST | `/datasets/upload` |
| GET | `/projects/{id}/dashboard` |
| GET | `/projects/{id}/anomalies` |
| POST | `/projects/{id}/query` |
| POST | `/projects/{id}/report/generate` |
| GET | `/projects/{id}/report/{report_id}` |
| GET | `/projects/{id}/report/{report_id}/export` |

Conventions:

- Routes stay thin: validate → call a service → serialise. No business logic in `api/`.
- Pydantic schemas in `schemas/` are the API contract; never return ORM objects directly.
- Upload and report generation run through `BackgroundTasks` — return a job/resource id, then
  poll, rather than blocking the request.
- Dashboard and anomaly endpoints must respond **with the LLM unavailable**
  (`architecture.md` → graceful degradation).
