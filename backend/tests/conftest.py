"""Test fixtures using pgserver for a throwaway Postgres."""

import contextlib
import os
from collections.abc import Iterator

import pgserver
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from alembic import command
from alembic import config as alembic_config
from app.db import engine as db_engine


class _GracefulSession(Session):
    """Session that silently recovers from flush errors (e.g. unique violations)
    so tests can catch the exception and then query the DB afterwards."""

    def flush(self):
        try:
            super().flush()
            self.commit()
        except Exception as exc:
            # Rollback the broken flush state, expire attributes, and
            # expunge objects so the session is usable again after the
            # test catches the exception.
            with contextlib.suppress(Exception):
                self.rollback()
            self.expire_all()
            self.expunge_all()
            raise exc


# Use the custom session class for all fixture sessions
def _make_graceful_session():
    """Factory for _GracefulSession instances bound to the test engine."""
    return _GracefulSession(bind=db_engine, autoflush=False)


@pytest.fixture(scope="session")
def pg_url(tmp_path_factory):
    """Start a throwaway Postgres via pgserver for the entire test session."""
    datadir = tmp_path_factory.mktemp("pg")
    srv = pgserver.get_server(datadir)
    url = srv.get_uri().replace("postgresql://", "postgresql+psycopg://", 1)
    yield url
    srv.cleanup()


@pytest.fixture(scope="session")
def pg_migrate(pg_url):
    """Run Alembic migrations against the pgserver URL (session-scoped)."""
    old_url = os.environ.get("DATABASE_URL")

    # Rebind engine to pgserver URL
    new_engine = create_engine(pg_url, pool_pre_ping=True)
    import app.db

    app.db.engine = new_engine
    app.db.engine.dispose()
    db_engine.__dict__.clear()
    db_engine.__dict__.update(new_engine.__dict__)

    os.environ["DATABASE_URL"] = pg_url

    try:
        alembic_cfg = alembic_config.Config("alembic.ini")
        command.upgrade(alembic_cfg, "head")
    finally:
        if old_url is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = old_url


@pytest.fixture()
def db(pg_url, pg_migrate) -> Iterator[Session]:
    """Provide a database session with truncated tables between tests."""
    session = _make_graceful_session()
    yield session
    # Clean up
    try:
        session.execute(text("DELETE FROM reading"))
        session.execute(text("DELETE FROM node"))
        session.commit()
    except Exception:
        session.rollback()
    session.close()
