# The core experiment — FR-D2 + FR-D5

The grounded summary generator and the naive/grounded comparison switch are the project's
research contribution and the paper's central chapter. **Quality over speed — do not rush
these to move on to other work.**

FR-D2 is a Must and FR-D5 is a Should, so D5 formally waits for the Must tier — but it is the
first Should to start, ahead of the lower-effort export/chart items.

## Design consequence: swappable prompting strategy from day one

Build FR-D2's prompt construction behind a **strategy interface** from the first commit, so
that adding the naive baseline in FR-D5 is a *new implementation*, not a refactor of working
code.

Both strategies take the same inputs and are selected at call time:

- **Grounded** — receives only the precomputed KPI JSON and anomaly list, with instructions
  forbidding it from citing numbers absent from that input.
- **Naive** — receives the raw issue data directly. This is the deliberate experimental
  baseline for measuring hallucination rate.

**The naive mode is the experiment, not an anti-pattern.** Never delete it, never "clean it
up", never flag it as a code smell. It is exempt from the Simplicity First principle in the
root `CLAUDE.md`.

## Reproducibility (binding — the experiment is invalid without this)

`temperature` / `top_p` / `top_k` are **removed on current frontier models** — Claude Opus
4.8 and 4.7 reject them with a 400 error. Determinism cannot come from `temperature=0`.
It comes from the two rules below.

### 1. Pin the model ID as a constant

**Pinned: `claude-opus-4-8`**, via `ANTHROPIC_MODEL_ID` in `.env`, read through
`core/config`. Never hard-code the string anywhere else, and never let a call site pick a
model.

A model change partway through the project makes the grounded and naive arms
**incomparable** — an entire dissertation chapter's worth of data becomes unusable. Record
the ID on every logged call so a change is visible in the data rather than silent.

Depth is controlled by `output_config={"effort": ...}` (`ANTHROPIC_EFFORT`, default `high`).
Treat effort as pinned too: it changes output length and reasoning, so sweeping it mid-study
has the same invalidating effect as swapping the model. If you tune it, re-run **both** arms.

### 2. Persist everything needed to re-score later

Every LLM call writes a `query_logs` row containing **all** of:

| Field | Why |
|---|---|
| `raw_prompt` | Exactly what was sent, after templating |
| `raw_response` | Exactly what came back, unparsed |
| `model_id` | Detects mid-project model drift |
| `prompting_strategy` | `grounded` \| `naive` — the experimental condition |
| `grounding_payload` | The exact KPI/anomaly JSON supplied as ground truth |
| `latency_ms` | Reported in the evaluation chapter |

**Why `grounding_payload` is the one that matters most:** hallucination rate is computed
*after the fact* by checking every number the model cited against the payload it was given.
If only the final answer text is stored, that check can never be performed — the metric
becomes permanently uncomputable and the runs have to be repeated from scratch.

Treat these writes as part of the feature, not as logging that can be added later.

## What gets measured

- **Hallucination rate** — numbers cited that do not appear in `grounding_payload`, scored
  per condition on identical datasets.
- **Anomaly detection F1** — against the FR-A4 ground-truth manifest (`scope.md`).
- **NL2SQL accuracy** — against the predefined question set, target >80% (`scope.md`).
- **Usability** — SUS, target >68 (PRD §5).

Both prompting conditions must run on **identical datasets** containing injected anomalies of
known type and location. Any difference other than the prompting strategy invalidates the
comparison.
