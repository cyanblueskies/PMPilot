# Testing

Test plan: `docs/Project_Requirements.md` §9. Tests live in `backend/tests/`.

**`pytest` and `httpx` are not installed yet.** Install them when writing the first test;
add them to `requirements.txt` in the same change.

## What must be tested, and why it's not optional

The dissertation claims the deterministic track is *"reproducible, verifiable, and
unit-testable in isolation"* (`architecture.md`). **That claim needs tests to exist to be
true.** They are evidence for the evaluation chapter, not housekeeping — write them alongside
the feature, not in a cleanup pass at the end.

Priority order:

1. **Analytics engine** (`services/analytics`) — every KPI, with hand-checked expected values
2. **Anomaly detection** (`services/anomaly`) — including the boundary cases where a Z-score
   or IQR threshold flips
3. **Ingestion / field mapping** — malformed CSV, missing columns, mixed timezone offsets
4. **API routes** — via `httpx` against the FastAPI app
5. **Prompt strategies** — that grounded mode's prompt contains **no raw issue rows**
   (see below)

## Structure: Arrange–Act–Assert

```python
def test_velocity_excludes_unfinished_issues():
    # Arrange
    sprint = make_sprint(issues=[done(5), done(3), in_progress(8)])
    # Act
    result = compute_velocity(sprint)
    # Assert
    assert result == 8
```

One behaviour per test. The name states the behaviour, not the function under test.

## No LLM calls in the test suite

Tests must run offline, deterministically, and for free.

- The deterministic track has no LLM dependency at all — test it directly.
- For the generative track, test **prompt construction**, not model output: assert the
  rendered prompt contains the expected KPI values, and — for grounded mode — assert it
  contains no raw issue rows. That assertion is the automated guard on the project's central
  rule; write it early.
- Model responses are evaluated separately, from the persisted `query_logs` rows
  (`experiment.md`), not from live calls inside `pytest`.

## Fixtures

Use the FR-A4 generator with a **fixed seed** for anything needing realistic data
(`scope.md`). Its ground-truth manifest doubles as the expected-value source for detection
tests. Keep fixtures small — a three-sprint dataset that a human can verify by hand beats a
large one nobody has checked.

## Verification discipline

When reporting that something works, say what you actually ran. If tests fail, show the
output. If a step was skipped, say so. "Should work" is not verification.

```powershell
pytest                          # all
pytest tests/test_kpi.py::test_velocity_excludes_unfinished_issues   # one
```
