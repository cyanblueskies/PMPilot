# PMPilot — Feature inventory and delivery schedule

Requirements: `docs/Project_Requirements.md` §4 · Priority rules: `.claude/rules/scope.md`
Phase boundaries: `docs/PRD.md` §10 (W1–W24) — the technical spec's §10 only covers W7 onward.

**Week numbers are relative. Pin W1 to a real calendar date and fill the Dates column.**

---

## 1. Feature inventory — 30 requirements

### Module A — Data ingestion (4)

| ID | Requirement | Priority | Acceptance |
|---|---|---|---|
| FR-A1 | Upload CSV / XLSX Jira-style export | Must | 100% success on schema-conforming samples |
| FR-A2 | Auto-detect / map key fields (Issue Key, Type, Status, Assignee, Story Point, Sprint, Created/Resolved Date) | Must | Clear error when a key field is missing |
| FR-A3 | Data cleaning (nulls, date normalisation, bad characters) | Must | No parse errors after cleaning |
| FR-A4 | Synthetic data generator | *Should → **treated as Must prerequisite*** | One command generates a dataset with configurable size and anomaly ratio |

> **FR-A4 is promoted.** Injected anomalies are the only ground truth for detection F1, and no
> real enterprise Jira data exists. PRD §10 already places it in W4–6 — before any detection
> work. Requires a fixed seed and a separate ground-truth manifest (`.claude/rules/scope.md`).

### Module B — Deterministic analytics (6)

| ID | Requirement | Priority | Acceptance |
|---|---|---|---|
| FR-B1 | Sprint velocity | Must | Matches hand calculation |
| FR-B2 | Burndown / burnup trend | Must | Chart data points match source |
| FR-B3 | Cycle time and lead time | Must | Sampled error < 1% |
| FR-B4 | Defect density / bug ratio | Must | Matches hand calculation |
| FR-B5 | Scope creep ratio | Should | — |
| FR-B6 | Workload distribution across team | Should | — |

### Module C — Anomaly detection (5)

| ID | Requirement | Priority | Acceptance |
|---|---|---|---|
| FR-C1 | Z-score / IQR velocity-drop detection | Must | Recall > 0.7 on synthetic anomaly set |
| FR-C2 | Overdue task pileup | Must | — |
| FR-C3 | Blocked-task clustering | Must | — |
| FR-C4 | Estimation-bias detection (story points vs actual) | Should | — |
| FR-C5 | Isolation Forest multivariate detection | Could | Comparison vs rule-based written up in the paper |

### Module D — LLM layer (5)

| ID | Requirement | Priority | Acceptance |
|---|---|---|---|
| FR-D1 | NL2SQL over structured fields only | Must | > 80% accuracy on the predefined question set |
| FR-D2 | **Grounded summary** — KPI + anomalies in, no un-supplied numbers | Must | Every number in a sampled summary traces to source data |
| FR-D3 | Management recommendations derived from the summary | Must | — |
| FR-D4 | RAG Q&A over issue descriptions / comments | Should → **deferred** | Top-K relevance > 70% (human-assessed) |
| FR-D5 | **Naive vs grounded prompt switch** | Should → **highest of the Shoulds** | Both modes runnable on one dataset |

> **FR-D2 + FR-D5 are the research contribution.** Build D2's prompting behind a swappable
> strategy from the first commit so D5 is a new implementation, not a refactor.
> **FR-D4 conflicts with the spec's milestone table** (which puts RAG in Sprint 3);
> `.claude/rules/scope.md` defers it until every Must is done. The rules file wins.

### Module E — Dashboard (4)

| ID | Requirement | Priority |
|---|---|---|
| FR-E1 | Core KPI cards (velocity, cycle time, defect rate) | Must |
| FR-E2 | Burndown and velocity trend charts | Must |
| FR-E3 | Anomaly / risk list, click through to related issues | Must |
| FR-E4 | Chart interaction (tooltips, time-range filter) | Should |

### Module F — Chat and reporting (4)

| ID | Requirement | Priority |
|---|---|---|
| FR-F1 | Natural-language chat panel | Must — *single-turn only; see below* |
| FR-F2 | Answers carry traceable evidence (which KPIs / issues) | Must |
| FR-F3 | One-click executive summary | Must |
| FR-F4 | Export report to PDF / Word | Should |

> **FR-F1 is classified three ways across the specs** (FR-F1 Must, PRD §3.3 Should, PRD §6
> Could). Default: single-turn Q&A with traceable evidence is the Must; multi-turn follow-up
> is Could — not built unprompted.

### Module G — Account / project management (2)

| ID | Requirement | Priority |
|---|---|---|
| FR-G1 | Single-user session management (no RBAC) | Should |
| FR-G2 | Save multiple historical uploaded datasets | Could |

### Totals

| Priority | Count | IDs |
|---|---|---|
| **Must** | 19 | A1–A3, B1–B4, C1–C3, D1–D3, E1–E3, F1–F3 |
| **Should** | 9 | A4\*, B5, B6, C4, D4†, D5, E4, F4, G1 |
| **Could** | 2 | C5, G2 |

\* promoted to Must prerequisite  ·  † deferred below all other Shoulds

**Won't have** (documented in Limitations): enterprise RBAC; live Jira / Azure DevOps API
integration; native mobile app.

---

## 2. Schedule — W1 to W24

### Phase 1 · W1–W3 — Requirements and research

PRD §10 deliverables: this PRD, the requirements document, a literature review draft.

| Week | Backend | Frontend | Paper / other |
|---|---|---|---|
| W1 | — | — | Topic scoping · supervisor meeting · reading |
| W2 | — | — | **`docs/PRD.md`** · personas · MoSCoW |
| W3 | — | — | **`docs/Project_Requirements.md`** · lit-review draft (§2.1–2.5) |

**Status: done.** Both spec documents exist. The lit review is drafted but needs its
citations — the two `[ref]` gaps (PM data literacy; LLM hallucination on tabular data) are
still open and block §2.3.

### Phase 2 · W4–W6 — Architecture and data preparation

PRD §10 deliverables: system architecture, database schema, **synthetic data generator**.

| Week | Backend | Frontend | Paper / other |
|---|---|---|---|
| W4 | Two-track architecture · layering · API surface | Stack decision (React 19 + Vite + TS) | Architecture written into spec §5 |
| W5 | DB schema design (§5.3) · Docker Postgres · read-only role · `.env` convention | Vite scaffold · oxlint | UML: use-case, component, ER |
| W6 | **FR-A4 generator** · fixed seed · anomaly injection · **ground-truth manifest** | Layout shell · routing · API client stub | Sample datasets committed · ch.3 Background draft |

**Status: partially done — this is where you are.** Architecture (§5), schema (§5.3), Docker
Postgres, and the rules files are done. **FR-A4 is not written; it is the immediate next
task.** UML diagrams not started.

### Phase 3 · W7–W10 — Sprint 1: ingestion and analytics

| Week | Backend | Frontend | Paper / other |
|---|---|---|---|
| W7 | ORM models · **wire Alembic** (`target_metadata`, real URL) · first migration · FastAPI app object · health endpoint | Clean Vite starter · layout · router · TS types from schemas | **CI/CD pipeline** · first public deploy · **PM interview + baseline questionnaire** |
| W8 | **FR-A1** upload endpoint · file/size validation · `BackgroundTasks` | Upload page · progress · error states | **Freeze requirements + acceptance thresholds** |
| W9 | **FR-A2** field mapping · **FR-A3** cleaning · UTC normalisation · ingestion tests | Field-mapping UI (confirm / correct detected columns) | Test plan (§9) |
| W10 | **FR-B1–B4** velocity · burndown · cycle/lead time · defect density · `kpi_snapshots` writes · KPI unit tests | Chart library decision + spike · dashboard skeleton | ch.4 Specification draft |

### Phase 4 · W11–W14 — Sprint 2: detection and grounded generation

| Week | Backend | Frontend | Paper / other |
|---|---|---|---|
| W11 | Dashboard endpoint · aggregation · perf check (**<5s @ 5,000 issues**) | **FR-E1** KPI cards · **FR-E2** burndown + velocity charts | ch.5 Design draft |
| W12 | **FR-C1–C3** Z-score/IQR · overdue pileup · blocked clustering · `anomalies` writes · **F1 harness vs manifest** | **FR-E3** anomaly list · issue drill-through | **First F1 number recorded** |
| W13 | **FR-D2** strategy interface · grounded prompt builder · `anthropic` SDK · **full `query_logs` write path** · no-raw-rows test | Summary panel · loading / streaming states | Prompt design documented for ch.6 |
| W14 | **FR-D3** recommendations · **FR-F3** exec summary endpoint · LLM-failure degradation | Exec summary UI · **LLM-down empty states** | ch.6 Implementation draft |

### Phase 5 · W15–W17 — Sprint 3: NL2SQL, chat, close the Musts

| Week | Backend | Frontend | Paper / other |
|---|---|---|---|
| W15 | **FR-D1** question set (~20 Q) · schema description · SQL generation · **statement whitelist + read-only connection** · row limit + timeout · accuracy harness | Query input · result table · out-of-scope message | Question set documented as an appendix |
| W16 | **FR-F2** evidence attribution · **FR-G1** session management | **FR-F1** chat panel · evidence display (which KPIs/issues) | — |
| W17 | **FR-D5** naive strategy + mode toggle · hardening · **all 19 Musts done** | Responsive pass · polish · empty/error states | **Public deploy** · demo path rehearsed |

### Phase 6 · W18–W20 — Evaluation

No new features. Backend/frontend work is bug-fix only.

| Week | Work | Paper |
|---|---|---|
| W18 | Run **both prompting arms** on identical datasets · hallucination scoring from `query_logs` · detection F1 · NL2SQL accuracy | Results tables |
| W19 | **User testing** — recruit, task scripts, sessions, **SUS**, task success rate | Raw data + transcripts to appendix |
| W20 | Analysis · figures · significance where applicable | **ch.7 Evaluation** written |

### Phase 7 · W21–W24 — Shoulds, writing, submission

| Week | Backend | Frontend | Paper |
|---|---|---|---|
| W21 | **FR-B5, B6** scope creep + workload · (FR-C4 if time) | **FR-E4** chart interaction · **FR-F4** export UI | — |
| W22 | Bug fix only | Bug fix only | ch.3–6 finalised |
| W23 | Freeze | Freeze | **ch.1, 2, 8** · demo video |
| W24 | — | — | Proofread · appendices · **submit** |

### Fixed checkpoints

| End of | Must be true |
|---|---|
| W6 | FR-A4 produces a dataset **and** a ground-truth manifest |
| W7 | CI green, deployed publicly, PM interview done (baseline data can't be collected retroactively) |
| W8 | Requirements + acceptance thresholds **frozen** — they are the Evaluation chapter's yardstick; changing them later invalidates it |
| W10 | Deterministic track computes real KPIs from an uploaded file, with tests |
| W12 | Detection F1 is **a number you can quote**, not a plan |
| W14 | End-to-end demo: upload → dashboard → anomalies → grounded summary |
| W17 | **All 19 Musts complete.** Publicly deployed. Only now may FR-D4 be considered |
| W20 | All evaluation data collected. **No new features after this** |

### Slack

W17, W22 and W24 are deliberately light. Absorb overruns there rather than compressing
W18–W20 — evaluation is itself a Must and cannot be rushed.

### Frontend / backend balance

Frontend is light in W7–W10 (there is nothing to visualise yet) and heavy in W11–W16.
The W7–W10 frontend slots are deliberately foundational — router, types, API client, upload
UI, chart-library spike — so that W11 starts with plumbing already proven. Don't defer them:
choosing the chart library in W11 under time pressure is the classic way this schedule slips.

---

## 3. Commit practice

The plan assumes small, frequent commits — most cells above are 1–2 working sessions.

- **Conventional Commits**: `feat(analytics): add cycle time calculation`,
  `test(anomaly): cover IQR boundary`, `docs(report): draft ch.7 intro`.
- Reference the requirement in the body: `Implements FR-B3.` The git history then doubles as
  a traceability matrix — direct evidence for the Implementation chapter.
- One branch per requirement (`feat/fr-b3-cycle-time`), merged to `master` when CI is green.
- **Dissertation chapters are committed too** — writing weeks should still show activity.
- **Never commit**: `.env`, real API keys, or any uploaded dataset.
