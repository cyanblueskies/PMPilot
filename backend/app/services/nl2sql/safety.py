"""SQL validation for FR-D1.

Defence layer 1 of the three in .claude/rules/security.md. All layers are
required, not alternatives:

1. this module — statement-type whitelist, enforced on a parsed AST
2. execution on a role with SELECT-only grants (services/nl2sql/execute.py)
3. a row limit and a statement timeout (same module)

Validation is done against a parsed tree, never by string matching. Searching
for "DROP" in the text is trivially defeated by a comment, a quoted identifier,
or different whitespace, and would give a false sense of safety.
"""

from __future__ import annotations

from dataclasses import dataclass

import sqlglot
from sqlglot import exp

DIALECT = "postgres"

# Tables a generated query may read. Anything else — including Postgres
# catalogue tables — is refused, so a query cannot enumerate the schema or read
# rows the feature was never meant to expose.
ALLOWED_TABLES = frozenset(
    {"projects", "sprints", "issues", "kpi_snapshots", "anomalies"}
)

# Expression types that mutate or leak. Checked by node type on the AST, so
# spelling, casing and comments are irrelevant.
FORBIDDEN_NODES = (
    exp.Insert,
    exp.Update,
    exp.Delete,
    exp.Drop,
    exp.Create,
    exp.Alter,
    exp.TruncateTable,
    exp.Grant,
    exp.Command,  # anything sqlglot could not classify, e.g. COPY, VACUUM
)

MAX_ROWS = 200


class UnsafeQuery(ValueError):
    """The generated SQL was rejected. The message is safe to show a user."""


@dataclass
class ValidatedQuery:
    sql: str
    tables: list[str]
    row_limit: int


def _filters_by_project(tree: exp.Expression, project_id: int) -> bool:
    """Is there an actual `project_id = <project_id>` comparison?

    Checked on the AST. Searching the rendered SQL for the number instead is
    satisfied by any incidental occurrence — `LIMIT 1` passes the test when
    project_id is 1 — so it asserts a guarantee it does not provide.
    """
    for comparison in tree.find_all(exp.EQ):
        for left, right in (
            (comparison.left, comparison.right),
            (comparison.right, comparison.left),
        ):
            if not isinstance(left, exp.Column) or left.name.lower() != "project_id":
                continue
            if isinstance(right, exp.Literal) and right.name == str(project_id):
                return True
    return False


def validate(sql: str, project_id: int) -> ValidatedQuery:
    """Parse, check and bound a generated statement.

    Returns the SQL to execute, which may differ from the input: a LIMIT is
    added when absent. Raises UnsafeQuery on anything else.
    """
    text = (sql or "").strip().rstrip(";").strip()
    if not text:
        raise UnsafeQuery("The model did not produce a query.")

    try:
        statements = sqlglot.parse(text, read=DIALECT)
    except Exception as exc:  # noqa: BLE001
        raise UnsafeQuery(f"The generated query could not be parsed: {exc}") from exc

    statements = [s for s in statements if s is not None]
    if len(statements) != 1:
        # Stacked statements are the classic way to smuggle a write past a
        # check that only inspects the first one.
        raise UnsafeQuery(
            f"Expected exactly one statement, found {len(statements)}."
        )

    tree = statements[0]

    if not isinstance(tree, exp.Select):
        # WITH ... SELECT parses as a Select carrying a `with` argument, so CTEs
        # still pass; only genuinely non-SELECT roots are rejected here.
        raise UnsafeQuery(
            f"Only SELECT statements are allowed, got {type(tree).__name__.upper()}."
        )

    for node_type in FORBIDDEN_NODES:
        found = list(tree.find_all(node_type))
        if found:
            raise UnsafeQuery(
                f"Statement contains a forbidden operation: "
                f"{type(found[0]).__name__.upper()}."
            )

    # CTE names appear as tables at their use site. They are defined inside the
    # query itself, so checking them against ALLOWED_TABLES rejects perfectly
    # ordinary SQL — and a generator that writes good SQL writes CTEs.
    cte_names = {
        cte.alias_or_name.lower() for cte in tree.find_all(exp.CTE) if cte.alias_or_name
    }

    tables = sorted(
        {
            t.name.lower()
            for t in tree.find_all(exp.Table)
            if t.name and t.name.lower() not in cte_names
        }
    )
    unknown = [t for t in tables if t not in ALLOWED_TABLES]
    if unknown:
        raise UnsafeQuery(
            "Query refers to tables that are not available: "
            + ", ".join(unknown)
        )
    if not tables:
        raise UnsafeQuery("Query does not read from any known table.")

    # Every readable table is project-scoped, so a query that forgets to filter
    # would return another project's rows.
    if "issues" in tables or "sprints" in tables:
        if not _filters_by_project(tree, project_id):
            raise UnsafeQuery(
                "Query must filter by the current project_id."
            )

    existing_limit = tree.args.get("limit")
    if existing_limit is None:
        tree = tree.limit(MAX_ROWS)
    else:
        try:
            requested = int(existing_limit.expression.name)
            if requested > MAX_ROWS:
                tree = tree.limit(MAX_ROWS)
        except (AttributeError, ValueError):
            tree = tree.limit(MAX_ROWS)

    return ValidatedQuery(
        sql=tree.sql(dialect=DIALECT),
        tables=tables,
        row_limit=MAX_ROWS,
    )
