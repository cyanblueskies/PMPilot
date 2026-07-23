# Scope and priority (binding)

Strict MoSCoW order: **finish every Must before starting any Should.** Could items are built
only on explicit request. Won't items are excluded by decision, not by omission.

## Must — the core loop, in this order

1. Upload / field mapping (FR-A1–A3)
2. KPI computation + dashboard (FR-B1–B4, FR-E1–E3)
3. Statistical anomaly detection (FR-C1–C3)
4. Grounded summary + recommendations (FR-D2, FR-D3)
5. NL2SQL over structured fields (FR-D1)
6. Quantitative evaluation and user-testing loop (PRD §6, docs §8)

**Evaluation is itself a Must**, not a post-hoc activity. The instrumentation that feeds it
(`query_logs`, `kpi_snapshots`, anomaly ground-truth comparison) ships *with* the features
it measures, not after.

### FR-A4 is a Must-tier prerequisite

The synthetic data generator is nominally a Should, but the Must-tier evaluation loop depends
on it: injected anomalies are the only source of ground truth for detection F1, and no real
enterprise Jira data is available. Build it first.

Two requirements on its output:

- **Fixed random seed.** Without it, every run produces a different dataset, your evaluation
  numbers are not reproducible, and nobody can regenerate the figures in the dissertation.
- **A separate machine-readable ground-truth manifest** alongside the CSV, recording which
  sprints/issues carry which injected anomaly type. It must be a *separate file* — if the
  answers live inside the CSV the system can see them and the evaluation is invalid.

## Should — after all Musts, in this order

1. **FR-D5, naive vs grounded comparison** — highest of the Shoulds; start it first, ahead of
   the lower-effort chart/export items. See `experiment.md`.
2. FR-B5/B6 (scope creep, workload distribution), FR-E4 (chart interaction), FR-F4 (PDF/Word
   export)
3. **FR-D4, RAG** — lowest priority in the entire plan. See below.

### FR-D1 NL2SQL — bounded scope for MVP

Support a **limited, predefined set of question types** over structured fields — the kind the
KPI/issue schema answers directly ("who has the most blocked tasks this sprint?"). Do not
chase open-ended arbitrary natural language.

Questions outside the supported set get a friendly out-of-scope message rather than a wrong
answer; the docs name this explicitly as the mitigation for NL2SQL accuracy risk. The **>80%
accuracy target is measured against that predefined question set**, not against arbitrary input.

### FR-D4 RAG — not yet

Do not start until every Must is complete and time genuinely allows. Concretely, until then:

- **Do not add pgvector, embedding models, or any vector-store dependency.**
- **Do not build "RAG-ready" abstractions in anticipation.**

RAG is designated as degradable to Could if time runs short, so the core loop must not depend
on it in any way.

## Could — do not build unprompted

Multi-project / multi-sprint comparison; velocity trend forecasting; FR-C5 (Isolation Forest
multivariate detection); FR-G2 (saved historical datasets).

Note FR-C5 appears in the risk table as the planned mitigation *if* rule-based detection is
judged to lack technical depth — it stays a Could until that call is made explicitly.

## Won't — excluded by decision, documented in the paper's Limitations

Enterprise RBAC; live Jira / Azure DevOps API integration (file import only); native mobile app.

## Unresolved in the source docs

Multi-turn follow-up questioning is classified inconsistently: FR-F1 calls the chat panel with
连续追问 a **Must**, PRD §3.3 lists David's 追问细节 story as a **Should**, and PRD §6 lists
针对某条洞察的追问式多轮对话 under **Could**.

Pending a decision: treat a working **single-turn Q&A panel with traceable evidence**
(FR-F1/FR-F2) as the Must, and deeper multi-turn conversational follow-up as Could — i.e.
do not build it unprompted.
