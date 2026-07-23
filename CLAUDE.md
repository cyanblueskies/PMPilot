# CLAUDE.md

## Project

**PMPilot** — an AI decision support platform for agile/Jira-style project management:
statistical anomaly detection + LLM grounded generation + NL2SQL. Birmingham CS Final Year
Project (target: First Class).

- Product spec: `docs/PRD.md` · Technical spec: `docs/Project_Requirements.md`
- Both are Chinese and are the **authoritative source of truth** — code is downstream of them.
  Requirements have IDs (`FR-A1`, `FR-B3`, …); use them when discussing scope.
- The dissertation is a deliverable alongside the code: **English, 10,000 words**.

## The one rule that overrides everything

**The LLM never receives raw issue tables.** It receives only precomputed structured results
(KPI JSON, anomaly lists) from the deterministic track, and is instructed never to cite a
number absent from that input. This is *grounded generation* — the project's core
contribution and the basis of its evaluation chapter. If a change would let raw issue rows
reach a prompt, stop and say so before writing it.

## Working principles

Bias toward caution over speed; for trivial tasks, use judgment.

**Think before coding.** State assumptions explicitly; if uncertain, ask. If multiple
interpretations exist, present them rather than picking silently. If a simpler approach
exists, say so. If something is unclear, stop and name what's confusing.

**Simplicity first.** Minimum code that solves the problem. No features beyond what was
asked, no abstractions for single-use code, no unrequested configurability, no error handling
for impossible scenarios. If 200 lines could be 50, rewrite it.
*Exception:* the FR-D5 naive baseline and the swappable prompting strategy are deliberate
experimental apparatus, not over-engineering — see `.claude/rules/experiment.md`.

**Surgical changes.** Touch only what you must. Don't improve adjacent code, refactor what
isn't broken, or reformat. Match existing style. Mention unrelated dead code; don't delete
it. Do remove imports/variables your own change orphaned. Every changed line should trace
to the request.

**Goal-driven execution.** Turn tasks into verifiable goals — "add validation" becomes
"write tests for invalid inputs, then make them pass". For multi-step work, state a brief
plan with a verification check per step, then loop until verified.

## Rules index — read the file before doing the work

These are **not** auto-loaded. Read the matching file *before* starting that kind of work,
not after. When rules conflict, the more specific file wins over this one.

| Read this | Before you |
|---|---|
| `.claude/rules/scope.md` | Pick what to build next, or are asked for anything not obviously in scope. **Binding MoSCoW order.** |
| `.claude/rules/architecture.md` | Touch `services/`, add a module, or wire the two tracks together |
| `.claude/rules/experiment.md` | Touch anything under `services/llm/`, prompts, `query_logs`, or FR-D2/D3/D5 |
| `.claude/rules/data-model.md` | Write ORM models, migrations, ingestion, or API routes |
| `.claude/rules/code-style.md` | Write Python at all — **pandas 3.0 and SQLAlchemy 2.0 break older idioms silently** |
| `.claude/rules/testing.md` | Write tests, or claim something is verified |
| `.claude/rules/security.md` | Touch NL2SQL, file upload, secrets, or anything handling user data |
| `.claude/rules/environment.md` | Run a command, add a dependency, or hit a setup failure |

## Settled decisions

- **Database: Docker Postgres 17** (`docker-compose.yml`, host port **5433**). Not SQLite —
  the code targets Postgres dialect throughout. A second **read-only role** exists solely for
  NL2SQL execution; see `.claude/rules/security.md`.
- **LLM: Claude, pinned to `claude-opus-4-8`.** The pin is load-bearing for the experiment —
  do not change it, and do not read the model name from anywhere but config
  (`.claude/rules/experiment.md`).

## Shell

PowerShell — chain with `;`, not `&&`.
