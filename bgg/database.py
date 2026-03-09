import sqlite3
from pathlib import Path


def open_db(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA foreign_keys = ON")
    _create_tables(conn)
    return conn


def _create_tables(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS ratings (
            user_id  TEXT    NOT NULL,
            bgg_id   INTEGER NOT NULL,
            rating   REAL    NOT NULL
        );

        CREATE TABLE IF NOT EXISTS game_stats (
            bgg_id            INTEGER PRIMARY KEY,
            high_rating_count INTEGER NOT NULL,
            total_raters      INTEGER NOT NULL
        );

        CREATE TABLE IF NOT EXISTS games (
            bgg_id         INTEGER PRIMARY KEY,
            name           TEXT    NOT NULL,
            year_published INTEGER,
            rating_avg     REAL,
            bgg_rank       INTEGER
        );

        CREATE TABLE IF NOT EXISTS metadata (
            key   TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
    """)
    conn.commit()


def create_indexes(conn: sqlite3.Connection) -> None:
    """Create indexes after bulk import. Call once, after import_ratings."""
    conn.executescript("""
        CREATE INDEX IF NOT EXISTS idx_ratings_bgg_id  ON ratings(bgg_id);
        CREATE INDEX IF NOT EXISTS idx_ratings_user_id ON ratings(user_id);
        CREATE INDEX IF NOT EXISTS idx_ratings_bgg_rtg ON ratings(bgg_id, rating);
    """)
    conn.commit()
