import sqlite3
import pytest
from bgg.database import open_db


def test_open_db_creates_tables(tmp_path):
    db_path = tmp_path / "test.db"
    conn = open_db(db_path)

    tables = {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
    }
    assert tables == {"ratings", "game_stats", "games", "metadata"}
    conn.close()


def test_open_db_is_idempotent(tmp_path):
    db_path = tmp_path / "test.db"
    conn1 = open_db(db_path)
    conn1.close()
    conn2 = open_db(db_path)  # must not raise
    conn2.close()
