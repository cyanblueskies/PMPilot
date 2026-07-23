# Code style

Match the surrounding code first. The rules below exist because the installed versions break
idioms that most examples, tutorials, and training data still use.

## pandas 3.0 — not 2.x

Installed: **pandas 3.0.3**. Code written from memory will be 2.x-style and can fail
**silently**.

**Copy-on-Write is mandatory.** Chained assignment no longer modifies the original frame —
and does not raise:

```python
df[df['status'] == 'Done']['cycle_time'] = 5   # WRONG — silently does nothing
df.loc[df['status'] == 'Done', 'cycle_time'] = 5   # correct
```

This is the most dangerous rule in the file: the failure is invisible until a KPI comes out
wrong, and it is hard to trace back.

Also changed:

- **`inplace=` is largely gone or ineffective.** Assign the result instead: `df = df.dropna()`.
- **Default string dtype is Arrow-backed.** Don't assume `object` dtype, and don't rely on
  `.astype(str)` producing NumPy object arrays.

When unsure, check behaviour against the installed version rather than recalling it.

## SQLAlchemy 2.0 style only

Installed: **SQLAlchemy 2.0.51**. Use the 2.0 declarative and query APIs exclusively:

```python
class Issue(Base):
    __tablename__ = "issues"
    id: Mapped[int] = mapped_column(primary_key=True)
    issue_key: Mapped[str] = mapped_column(index=True)

stmt = select(Issue).where(Issue.sprint_id == sprint_id)
rows = session.scalars(stmt).all()
```

**No legacy `session.query(...)`.** Mixing the two styles across modules is the failure mode
to avoid — pick 2.0 and stay there.

## Datetimes — UTC everywhere

Jira CSV exports carry timezone offsets. Cycle time and lead time are computed by subtracting
timestamps, and they are the deterministic track's headline output.

- **Parse to timezone-aware UTC at ingestion.** Never store naive datetimes.
- **Use `TIMESTAMPTZ`** for every timestamp column.
- **Compute in UTC**; convert to local time only for display, if at all.

Getting this wrong shifts every duration-based KPI by hours without any error, which then
poisons anomaly detection and the ground-truth comparison built on top of it.

## Python

- Type-hint public function signatures in `services/` — these are the modules under test.
- Keep `services/analytics` and `services/anomaly` free of framework and LLM imports
  (`architecture.md`).
- Pure functions where practical: KPI computation takes data in, returns values out, does not
  reach into the database or the request.

## Frontend

- **`npm run lint` is oxlint, not ESLint.** Don't add ESLint config or assume its rules.
- TypeScript strict — no `any` to silence an error; model the type.
- Dependencies are minimal by design. A chart library, router, and React Query are all
  *not yet installed* — add when first needed, and say so rather than assuming.
