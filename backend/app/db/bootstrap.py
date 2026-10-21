"""Bring the database to the shape the models expect, once per process.

This used to run in a startup hook. On serverless hosting there is no reliable
"startup": every cold instance boots on the request that woke it, and a hook
that inspects every table adds a few dozen round trips to that request. So:

* ``ensure_database_ready()`` runs the preparation lazily, on the first request
  a process serves, and remembers that it succeeded. A failure is not
  remembered, so the next request tries again rather than the instance staying
  broken until it is recycled.
* The preparation records a fingerprint of the mapped schema. A cold start
  whose models match the fingerprint costs one query; only a deploy that
  actually changed the models pays for ``create_all`` and the column sync.

The guarantee from before is unchanged: nothing here drops or rewrites data.
Seeding only ever happens through ``seed_if_empty``.
"""

from __future__ import annotations

import hashlib
import logging
import threading
from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import String, Text, select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Mapped, mapped_column

from app.core.config import get_settings
from app.db.migrations import missing_columns, sync_columns
from app.db.session import Base, SessionLocal, engine

log = logging.getLogger(__name__)

_FINGERPRINT_KEY = "schema_fingerprint"
# Arbitrary constant; identifies this app's lock among any others on the server.
_ADVISORY_LOCK_ID = 74_023_118
_lock = threading.Lock()
_ready = False


class AppState(Base):
    """Small key/value table for facts about the deployment itself."""

    __tablename__ = "app_state"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(Text)


def schema_fingerprint() -> str:
    """Hash of every mapped table and column. Changes when a model does."""

    parts = sorted(
        f"{table.name}.{column.name}:{column.type}"
        for table in Base.metadata.sorted_tables
        for column in table.columns
    )
    return hashlib.sha256("\n".join(parts).encode()).hexdigest()


def _stored_fingerprint() -> str | None:
    try:
        with SessionLocal() as db:
            return db.scalar(select(AppState.value).where(AppState.key == _FINGERPRINT_KEY))
    except SQLAlchemyError:
        # No app_state table yet: a fresh database, or one from before this
        # module existed. Either way the full preparation has to run.
        return None


def prepare_database(force: bool = False) -> None:
    """Create missing tables and columns, then seed a never-used database."""

    current = schema_fingerprint()
    if not force and _stored_fingerprint() == current:
        return

    with _exclusive():
        Base.metadata.create_all(bind=engine)
        added = sync_columns(engine, Base.metadata)
        if added:
            log.info("Schema migration added %d column(s): %s", len(added), ", ".join(added))

        if get_settings().seed_demo_data:
            from app.seed import seed_if_empty

            if seed_if_empty():
                log.info("Empty database detected — seeded demo data.")

        # Only remember a schema that fully arrived. If a column could not be
        # added, every cold start keeps retrying (and logging) until it is.
        if missing_columns(engine, Base.metadata):
            return
        with SessionLocal() as db:
            db.merge(AppState(key=_FINGERPRINT_KEY, value=current))
            db.commit()


@contextmanager
def _exclusive() -> Iterator[None]:
    """Serialize preparation across instances that cold-start together.

    Two instances woken by the same burst of traffic would otherwise both find
    an empty database and both try to seed it. Postgres has a lock for exactly
    this; SQLite is single-process here and needs none.
    """

    if engine.dialect.name != "postgresql":
        yield
        return
    with engine.connect() as connection:
        connection.execute(text("SELECT pg_advisory_lock(:k)"), {"k": _ADVISORY_LOCK_ID})
        try:
            yield
        finally:
            connection.execute(text("SELECT pg_advisory_unlock(:k)"), {"k": _ADVISORY_LOCK_ID})


def ensure_database_ready() -> None:
    global _ready
    if _ready:
        return
    with _lock:
        if _ready:
            return
        prepare_database()
        _ready = True
