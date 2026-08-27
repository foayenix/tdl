"""Shared fixtures. Every test gets its own file on disk — WAL needs a real one."""

from __future__ import annotations

import pytest

from ledger.db import connect
from ledger.migrate import migrate


@pytest.fixture
def db_path(tmp_path):
    return tmp_path / "ledger.sqlite"


@pytest.fixture
def conn(db_path):
    connection = connect(db_path)
    yield connection
    connection.close()


@pytest.fixture
def migrated(conn):
    """A connection to a database at the newest schema version."""
    migrate(conn)
    return conn
