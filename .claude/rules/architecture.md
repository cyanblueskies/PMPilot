# Architecture: two tracks, deliberately separated

This separation is the project's core engineering contribution and the basis of its
evaluation chapter. **Do not blur it.**

## Deterministic track

Ingestion → statistical analytics engine → anomaly detection.

Produces reproducible, independently verifiable facts:

- **KPIs** — velocity, cycle time, lead time, defect density, scope creep
- **Anomaly records** — Z-score/IQR velocity drops, overdue pileup, blocked-task clustering

Hard requirements:

- **Unit-testable in isolation**, with no LLM dependency and no FastAPI coupling. A test of
  the analytics engine must not import the web framework or touch the network.
- **Algorithms swappable without touching other modules** — detection is a strategy, not
  logic inlined into a route handler.
- Output must be **serializable to JSON**, because that JSON is exactly what the generative
  track receives (and what hallucinations are later scored against).

## Generative track

LLM orchestration over the deterministic track's **output only**.

**The critical rule: the LLM never receives raw issue tables.** It receives only the
precomputed structured results (KPI JSON, anomaly lists), with instructions forbidding it
from citing numbers absent from that input. This is *grounded generation*, and it is what
distinguishes the project from "call an LLM on a CSV".

`docs/Project_Requirements.md` §5.4 defines two engines plus a deliberate baseline:

1. **NL2SQL** — question + schema description → SELECT-only query → execute → LLM phrases
   the result set as prose. Bounded to a predefined question set for MVP (`scope.md`);
   query safety rules in `security.md`.
2. **RAG** — embeddings over `issues.description`/`comments`, Top-K retrieval, for
   open-ended "why" questions. **Deferred — do not implement or add dependencies**
   (`scope.md` → FR-D4).
3. **Naive vs grounded prompting** — a *switchable* comparison mode (FR-D5), the paper's
   core experiment. See `experiment.md`.

## Graceful degradation

**LLM failures must not break the dashboard.** KPI and anomaly views are required to keep
working with the LLM entirely unavailable. Treat the generative track as an enhancement layer
over a system that is already useful without it — never as a dependency of the core views.

## Backend layering

```
api/       routes — thin; no business logic
services/  ingestion · analytics · anomaly · llm
models/    SQLAlchemy ORM
schemas/   Pydantic validation
core/      config
```

Dependencies point one way: `api/` → `services/` → `models/`. Keep `services/analytics` and
`services/anomaly` free of both LLM and framework imports so they can be tested directly.

Long-running parse/compute work goes through FastAPI `BackgroundTasks`. Celery + Redis is
noted in the docs as a later option, **not a current dependency** — do not add it.

## Performance budget

500–5,000 issues and 5–20 sprints per project; **KPI + anomaly computation budgeted at <5s**
at that scale. If an approach can't hold that, say so before building it.
