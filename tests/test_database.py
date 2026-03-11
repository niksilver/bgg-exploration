import sqlite3
import pytest
from bgg.database import open_db, create_indexes


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


def test_create_indexes_includes_covering_index(tmp_path):
    conn = open_db(tmp_path / "test.db")
    create_indexes(conn)
    indexes = {row[0] for row in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='index'"
    )}
    assert "idx_ratings_usr_rtg_bgg" in indexes
    conn.close()


def test_open_db_migrates_existing_db_to_add_covering_index(tmp_path):
    # Simulate a DB that was created before the covering index was added
    db_path = tmp_path / "old.db"
    conn = sqlite3.connect(db_path)
    conn.executescript("""
        CREATE TABLE ratings (
            user_id TEXT NOT NULL,
            bgg_id  INTEGER NOT NULL,
            rating  REAL NOT NULL,
            PRIMARY KEY (user_id, bgg_id)
        );
        CREATE TABLE game_stats (
            bgg_id            INTEGER PRIMARY KEY,
            high_rating_count INTEGER NOT NULL,
            total_raters      INTEGER NOT NULL,
            rating_avg        REAL
        );
        CREATE TABLE games    (bgg_id INTEGER PRIMARY KEY, name TEXT NOT NULL);
        CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
    """)
    conn.close()

    conn = open_db(db_path)
    indexes = {row[0] for row in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='index'"
    )}
    conn.close()

    assert "idx_ratings_usr_rtg_bgg" in indexes


