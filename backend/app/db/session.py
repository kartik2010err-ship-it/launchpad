from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_settings

settings = get_settings()


def _engine_options(url: str) -> dict:
    """Connection settings that suit the database and where we are running.

    SQLite needs ``check_same_thread`` off because FastAPI serves sync routes
    from a thread pool. Postgres gets a deliberately small pool: on serverless
    hosting every warm instance holds its own, and a free-tier database caps
    total connections. ``pool_recycle`` sits under the five-minute idle window
    after which hosted Postgres (Neon, Supabase) suspends and drops sockets, and
    ``pool_pre_ping`` catches the ones that died while an instance was frozen.

    ``prepare_threshold=None`` turns off psycopg's automatic server-side
    prepared statements, which a transaction-mode connection pooler (Neon's
    ``-pooler`` host, Supabase's port 6543) can route to the wrong backend.
    """

    if url.startswith("sqlite"):
        return {"connect_args": {"check_same_thread": False}}
    return {
        "pool_pre_ping": True,
        "pool_size": 3,
        "max_overflow": 4,
        "pool_recycle": 240,
        "connect_args": {"prepare_threshold": None},
    }


engine = create_engine(settings.sqlalchemy_url, **_engine_options(settings.sqlalchemy_url))
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
