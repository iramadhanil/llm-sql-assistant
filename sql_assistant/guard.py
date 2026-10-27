"""Guardrails. A generated query has to pass two independent checks:

1. Static check (sqlglot): one statement, a SELECT at the top, no statement
   that writes or changes anything, and only known tables.
2. Read-only execution: the database is opened read-only, a time limit stops
   runaway queries, and at most max_rows rows are fetched.

Either layer alone would stop a destructive query. Having both means a gap in
one is still covered by the other.
"""

import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path

import sqlglot
from sqlglot import exp


class GuardError(ValueError):
    """The query was rejected before it reached the database."""


# Statement types that must never appear anywhere in a query.
_BLOCKED = tuple(
    getattr(exp, name)
    for name in (
        "Insert", "Update", "Delete", "Merge", "Drop", "Create", "Alter", "AlterTable",
        "Command", "Pragma", "Attach", "Detach", "Transaction", "Commit", "Rollback",
        "Set", "Use", "Copy", "LoadData", "Grant", "Revoke", "TruncateTable",
    )
    if hasattr(exp, name)
)

_ALLOWED_TOP = tuple(getattr(exp, name) for name in ("Select", "Union", "Intersect", "Except") if hasattr(exp, name))


def check_sql(sql: str, allowed_tables: set) -> None:
    """Raise GuardError if the query is not a single read-only SELECT over known tables."""
    if not sql or not sql.strip():
        raise GuardError("empty query")
    try:
        statements = [s for s in sqlglot.parse(sql, read="sqlite") if s is not None]
    except sqlglot.errors.ParseError as e:
        raise GuardError(f"could not parse the query: {e}") from None
    if len(statements) != 1:
        raise GuardError(f"expected one statement, got {len(statements)}")

    tree = statements[0]
    if not isinstance(tree, _ALLOWED_TOP):
        raise GuardError(f"only SELECT queries are allowed, got {tree.key.upper()}")

    for node in tree.walk():
        if isinstance(node, _BLOCKED):
            raise GuardError(f"{node.key.upper()} is not allowed")

    cte_names = {cte.alias_or_name.lower() for cte in tree.find_all(exp.CTE)}
    allowed = {t.lower() for t in allowed_tables} | cte_names
    for table in tree.find_all(exp.Table):
        name = table.name.lower()
        if name and name not in allowed:
            raise GuardError(f"unknown table: {table.name}")


@dataclass
class QueryResult:
    columns: list
    rows: list
    truncated: bool
    seconds: float


def run_query(db_path: Path, sql: str, max_rows: int = 1000, timeout_s: float = 20.0) -> QueryResult:
    """Run a query on a read-only connection with a time limit."""
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        con.execute("PRAGMA query_only = ON")
        deadline = time.monotonic() + timeout_s
        # SQLite calls this every 10,000 virtual-machine steps; returning 1 aborts the query.
        con.set_progress_handler(lambda: 1 if time.monotonic() > deadline else 0, 10_000)
        start = time.perf_counter()
        cursor = con.execute(sql)
        rows = cursor.fetchmany(max_rows + 1)
        seconds = time.perf_counter() - start
        columns = [d[0] for d in cursor.description or []]
    except sqlite3.OperationalError as e:
        if "interrupted" in str(e):
            raise sqlite3.OperationalError(f"query took longer than {timeout_s:.0f} seconds") from None
        raise
    finally:
        con.close()
    truncated = len(rows) > max_rows
    return QueryResult(columns=columns, rows=rows[:max_rows], truncated=truncated, seconds=seconds)
