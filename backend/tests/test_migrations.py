"""Additive-column migrations.

The failure this guards against is specific and expensive: a model gains a
column, ``create_all`` silently does nothing to the existing table, and the next
query against a live database with real student work in it fails. The tempting
fix at that point is to wipe and reseed, which is exactly how a season's data
gets lost.

These tests prove the column is added, existing rows survive it, and running the
migration repeatedly is harmless.
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def _fresh_engine(tmp_path, name="m.db"):
    return create_engine(f"sqlite:///{tmp_path / name}")


def test_a_new_column_is_added_to_a_populated_table(tmp_path) -> None:
    from app.db.migrations import sync_columns

    engine = _fresh_engine(tmp_path)

    class Base(DeclarativeBase):
        pass

    class Widget(Base):
        __tablename__ = "widgets"
        id: Mapped[int] = mapped_column(primary_key=True)
        name: Mapped[str] = mapped_column(sa.String(40))

    Base.metadata.create_all(engine)
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO widgets (id, name) VALUES (1, 'keeper')"))

    # The model grows a column, exactly as shipping a feature would.
    class Base2(DeclarativeBase):
        pass

    class Widget2(Base2):
        __tablename__ = "widgets"
        id: Mapped[int] = mapped_column(primary_key=True)
        name: Mapped[str] = mapped_column(sa.String(40))
        shared: Mapped[bool] = mapped_column(sa.Boolean, default=False)

    added = sync_columns(engine, Base2.metadata)
    assert "widgets.shared" in added

    columns = {c["name"] for c in inspect(engine).get_columns("widgets")}
    assert "shared" in columns

    with engine.begin() as conn:
        row = conn.execute(text("SELECT name, shared FROM widgets WHERE id = 1")).one()
    # The row is still there, and the new column was backfilled from its default.
    assert row[0] == "keeper"
    assert row[1] in (0, False)


def test_running_it_twice_changes_nothing(tmp_path) -> None:
    from app.db.migrations import sync_columns

    engine = _fresh_engine(tmp_path, "idem.db")

    class Base(DeclarativeBase):
        pass

    class Thing(Base):
        __tablename__ = "things"
        id: Mapped[int] = mapped_column(primary_key=True)
        label: Mapped[str] = mapped_column(sa.String(20), default="x")

    Base.metadata.create_all(engine)
    assert sync_columns(engine, Base.metadata) == []
    assert sync_columns(engine, Base.metadata) == []


def test_it_never_drops_a_column_the_model_no_longer_has(tmp_path) -> None:
    """Additive only. A removed attribute must not take the data with it."""

    from app.db.migrations import sync_columns

    engine = _fresh_engine(tmp_path, "keep.db")
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE notes (id INTEGER PRIMARY KEY, body TEXT, legacy TEXT)"))
        conn.execute(text("INSERT INTO notes VALUES (1, 'hello', 'do not lose me')"))

    class Base(DeclarativeBase):
        pass

    class Note(Base):
        __tablename__ = "notes"
        id: Mapped[int] = mapped_column(primary_key=True)
        body: Mapped[str] = mapped_column(sa.Text)

    sync_columns(engine, Base.metadata)

    with engine.begin() as conn:
        assert conn.execute(text("SELECT legacy FROM notes WHERE id = 1")).scalar() == (
            "do not lose me"
        )


def test_the_real_schema_needs_no_migration_when_freshly_created(tmp_path) -> None:
    """A database built by create_all is already correct — the migration is a
    no-op there, which is how we know it is not papering over a model bug."""

    from app.db.migrations import sync_columns
    from app.db.session import Base
    from app.main import app  # noqa: F401 — imports every model into the metadata

    engine = _fresh_engine(tmp_path, "real.db")
    Base.metadata.create_all(engine)
    assert sync_columns(engine, Base.metadata) == []


def test_the_new_workspace_setting_would_reach_a_live_database(tmp_path) -> None:
    """The concrete case this session introduced: members_can_create_teams was
    added to a model whose table already exists in production."""

    from app.db.migrations import sync_columns
    from app.db.session import Base
    from app.main import app  # noqa: F401

    engine = _fresh_engine(tmp_path, "live.db")
    Base.metadata.create_all(engine)

    # Simulate the pre-feature table by dropping the column back out.
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE workspaces DROP COLUMN members_can_create_teams"))
    assert "members_can_create_teams" not in {
        c["name"] for c in inspect(engine).get_columns("workspaces")
    }

    added = sync_columns(engine, Base.metadata)
    assert "workspaces.members_can_create_teams" in added
    assert "members_can_create_teams" in {
        c["name"] for c in inspect(engine).get_columns("workspaces")
    }


# --------------------------------------------------------------------------- #
# Dialect correctness
#
# These exist because of a real outage. The migration rendered a boolean
# default as `DEFAULT 1`, which SQLite accepts and Postgres rejects. Every test
# above runs against SQLite, so the whole suite passed while production —
# Postgres — silently failed the ALTER, left the column missing, and broke
# every query against that table. Testing one dialect is testing one dialect.
# --------------------------------------------------------------------------- #


def test_a_boolean_default_is_valid_postgres_not_just_valid_sqlite() -> None:
    import sqlalchemy as sa
    from sqlalchemy.dialects import postgresql

    from app.db.migrations import _default_clause

    clause = _default_clause(sa.Column("flag", sa.Boolean, default=True), postgresql.dialect())
    assert clause.strip().lower() == "default true"
    assert "default 1" not in clause.lower(), "Postgres rejects DEFAULT 1 on a boolean"

    false_clause = _default_clause(
        sa.Column("flag", sa.Boolean, default=False), postgresql.dialect()
    )
    assert false_clause.strip().lower() == "default false"


def test_defaults_render_per_dialect() -> None:
    import sqlalchemy as sa
    from sqlalchemy.dialects import postgresql, sqlite

    from app.db.migrations import _default_clause

    boolean = sa.Column("flag", sa.Boolean, default=True)
    assert _default_clause(boolean, sqlite.dialect()).strip().lower() in {
        "default 1",
        "default true",
    }
    assert _default_clause(boolean, postgresql.dialect()).strip().lower() == "default true"


def test_a_string_default_is_escaped_not_interpolated() -> None:
    import sqlalchemy as sa
    from sqlalchemy.dialects import postgresql

    from app.db.migrations import _default_clause

    clause = _default_clause(
        sa.Column("label", sa.String(20), default="it's"), postgresql.dialect()
    )
    assert clause == " DEFAULT 'it''s'"


def test_every_model_default_renders_for_postgres() -> None:
    """The real guard: walk the actual schema and make sure nothing in it
    would produce invalid Postgres on a live ALTER."""

    from sqlalchemy.dialects import postgresql

    from app.db.migrations import _default_clause
    from app.db.session import Base
    from app.main import app  # noqa: F401 — loads every model

    dialect = postgresql.dialect()
    for table in Base.metadata.sorted_tables:
        for column in table.columns:
            clause = _default_clause(column, dialect)
            if not clause:
                continue
            lowered = clause.lower()
            # The specific failure that caused the outage.
            if isinstance(column.type.as_generic(), type(column.type.as_generic())) and str(
                column.type
            ).upper().startswith("BOOLEAN"):
                assert lowered.strip() in {"default true", "default false"}, (
                    f"{table.name}.{column.name} would emit {clause!r}, which Postgres rejects"
                )


def test_an_incomplete_migration_is_reported(tmp_path, caplog) -> None:
    """A half-migrated schema must be loud. Silence is how a missing column
    becomes a mystery outage instead of a five-minute fix."""

    import logging

    import sqlalchemy as sa
    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

    from app.db.migrations import sync_columns

    engine = create_engine(f"sqlite:///{tmp_path / 'loud.db'}")
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE widgets (id INTEGER PRIMARY KEY)"))

    class Base(DeclarativeBase):
        pass

    class Widget(Base):
        __tablename__ = "widgets"
        id: Mapped[int] = mapped_column(primary_key=True)
        name: Mapped[str] = mapped_column(sa.String(20), default="x")

    # Force the ALTER to fail so the verification pass has something to find.
    import app.db.migrations as migrations

    original = migrations.CreateColumn
    with caplog.at_level(logging.ERROR):
        try:
            migrations.CreateColumn = lambda col: (_ for _ in ()).throw(RuntimeError("boom"))
            sync_columns(engine, Base.metadata)
        finally:
            migrations.CreateColumn = original

    assert any("MIGRATION INCOMPLETE" in record.message for record in caplog.records)
