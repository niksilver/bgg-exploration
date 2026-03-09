import sqlite3
import pytest
from unittest.mock import MagicMock
from bgg.api import GameDetails
from bgg.database import open_db, ensure_game_cached


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


def test_ensure_game_cached_inserts_on_first_call(tmp_path):
    conn = open_db(tmp_path / "test.db")
    details = GameDetails(bgg_id=266192, name="Wingspan", year=2019,
                          rating_avg=8.07, bgg_rank=21)
    client = MagicMock()
    client.fetch.return_value = details

    ensure_game_cached(266192, client, conn)

    row = conn.execute(
        "SELECT name, year_published, rating_avg, bgg_rank FROM games WHERE bgg_id=?",
        (266192,),
    ).fetchone()
    assert row == ("Wingspan", 2019, 8.07, 21)
    client.fetch.assert_called_once_with(266192)


def test_open_db_migrates_existing_db_to_add_rating_avg(tmp_path):
    # Simulate a pre-migration DB: create game_stats without rating_avg
    db_path = tmp_path / "old.db"
    conn = sqlite3.connect(db_path)
    conn.executescript("""
        CREATE TABLE game_stats (
            bgg_id            INTEGER PRIMARY KEY,
            high_rating_count INTEGER NOT NULL,
            total_raters      INTEGER NOT NULL
        );
    """)
    conn.close()

    conn = open_db(db_path)
    columns = {row[1] for row in conn.execute("PRAGMA table_info(game_stats)")}
    conn.close()

    assert "rating_avg" in columns


def test_game_stats_has_rating_avg_column(tmp_path):
    conn = open_db(tmp_path / "test.db")
    columns = {row[1] for row in conn.execute("PRAGMA table_info(game_stats)")}
    assert "rating_avg" in columns
    conn.close()


def test_ensure_game_cached_skips_api_if_already_present(tmp_path):
    conn = open_db(tmp_path / "test.db")
    conn.execute(
        "INSERT INTO games(bgg_id, name) VALUES (?, ?)", (266192, "Wingspan")
    )
    conn.commit()
    client = MagicMock()

    ensure_game_cached(266192, client, conn)

    client.fetch.assert_not_called()
