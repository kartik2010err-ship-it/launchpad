"""Additive schema migrations.

``Base.metadata.create_all`` creates missing *tables* but never alters existing
ones, so adding a column to a model that is already live in production is a
silent no-op: the model has the attribute, the table does not, and the first
query that touches it fails. That gap is what this module closes.

Scope is deliberately narrow. This adds missing columns and nothing else. It
will not drop, rename, retype or reorder anything, because those operations
cannot be made safe without knowing intent, and a tool that guesses at intent
against a database holding real student work is worse than no tool.

    add a column          -> handled here
    anything else         -> needs a real migration tool

It is idempotent, so it runs on every boot alongside ``create_all``. When this
project outgrows additive-only changes, the replacement is Alembic; until then
this stops the specific failure mode that costs a student their data.
"""

from __future__ import annotations

import logging

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.schema import CreateColumn

log = logging.getLogger(__name__)


def _default_clause(column) -> str:
    """The literal DEFAULT to backfill existing rows with, or ''.

    Only Python-side scalar defaults are translated. A callable default (say
    ``utcnow``) cannot be expressed as a constant, so the column is added
    nullable and left for the application to populate.
    """

    default = getattr(column, "default", None)
    if default is None or not getattr(default, "is_scalar", False):
        return ""
    value = default.arg
    if isinstance(value, bool):
        return f" DEFAULT {1 if value else 0}"
    if isinstance(value, (int, float)):
        return f" DEFAULT {value}"
    if isinstance(value, str):
        escaped = value.replace("'", "''")
        return f" DEFAULT '{escaped}'"
    return ""


def sync_columns(engine: Engine, metadata) -> list[str]:
    """Add every column a mapped table is missing. Returns what it added."""

    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    added: list[str] = []

    for table in metadata.sorted_tables:
        if table.name not in existing_tables:
            continue  # create_all just made it, or will.
        present = {col["name"] for col in inspector.get_columns(table.name)}
        for column in table.columns:
            if column.name in present:
                continue

            # A NOT NULL column with no default cannot be added to a table that
            # already has rows. Widen it to nullable rather than crash the boot;
            # the alternative is a server that refuses to start.
            spec = CreateColumn(column).compile(dialect=engine.dialect).string
            if " NOT NULL" in spec and not _default_clause(column):
                spec = spec.replace(" NOT NULL", "")
                log.warning(
                    "migration: %s.%s added as NULLABLE — a NOT NULL column needs a "
                    "default before it can be added to a populated table.",
                    table.name,
                    column.name,
                )

            statement = f"ALTER TABLE {table.name} ADD COLUMN {spec}{_default_clause(column)}"
            try:
                with engine.begin() as connection:
                    connection.execute(text(statement))
            except Exception:  # noqa: BLE001 — one bad column must not stop the rest
                log.exception("migration: could not add %s.%s", table.name, column.name)
                continue
            added.append(f"{table.name}.{column.name}")
            log.info("migration: added column %s.%s", table.name, column.name)

    return added
