# Security and data handling

This is a coursework project, not a production system — but three areas carry real risk and
two of them are graded (NFRs in `docs/Project_Requirements.md` §7; ethics and data privacy in
`docs/PRD.md` §9).

## NL2SQL — the highest-risk surface

An LLM generates SQL that then executes against the database. Defence is layered; **all
layers are required**, not alternatives:

1. **Whitelist statement types — SELECT only.** Reject anything else before execution:
   parse the statement and check its type. Do not rely on string matching for `DROP` /
   `DELETE` — that is trivially bypassed and is not a control.
2. **Execute on a read-only database connection.** A separate role with SELECT-only grants.
   This is the layer that holds when the first one is bypassed, so it must exist even though
   the whitelist is already there.
3. **Bound the result set** — a row limit and a statement timeout. A generated query can be
   accidentally catastrophic without being malicious.
4. **Never interpolate user text into SQL.** The model emits a query; it is validated and
   executed, never string-concatenated with the raw question.
5. **Out-of-scope questions get a refusal, not a guess** (`scope.md` → FR-D1).

Log every generated query to `query_logs` — it is both an audit trail and evaluation data.

## Secrets

- `.env` is gitignored. **Maintain a `.env.example`** listing every required key with dummy
  values, so the project is runnable from a clean clone.
- **Never commit an API key**, and never write one into source, tests, or fixtures.
- Read config through `core/config` (Pydantic settings), not scattered `os.getenv` calls.
- If a key is ever committed, treat it as compromised: rotate it, don't just delete the line.

## File upload (FR-A1)

Uploads are the only untrusted input path into the system:

- Validate extension **and** parsed content — accept CSV/XLSX only.
- Enforce a size cap and a row cap before parsing; reject early rather than OOM-ing the parser.
- Parse errors must return a clear message, never a stack trace to the client.
- Do not execute or evaluate anything from file contents (notably: spreadsheet formulas).

## Data privacy and ethics

- **No real enterprise Jira data.** The project runs on synthetic data (FR-A4) plus any data
  a user uploads themselves. This is a deliberate scope decision, recorded in PRD §9.
- Uploaded data may contain real names in `Assignee` / `Reporter`. Do not add features that
  publish, export, or transmit it beyond the user's own session without an explicit decision.
- **Nothing from an uploaded dataset goes into a git commit** — not as a fixture, not as a
  screenshot, not in a report artefact.
- For user testing, follow the ethics process in PRD §9; anonymise participants in the
  dissertation.

## LLM-specific

- The grounded path sends only computed KPI/anomaly JSON — this is a privacy property as well
  as a correctness one, and another reason not to blur the two tracks.
- The naive baseline **does** send raw rows to the model by design. That is the experiment;
  restrict it to synthetic datasets rather than real uploads.
