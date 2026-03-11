import sqlite3
from pathlib import Path


def open_db(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    _create_tables(conn)
    _migrate(conn)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _create_tables(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS ratings (
            user_id  TEXT    NOT NULL,
            bgg_id   INTEGER NOT NULL,
            rating   REAL    NOT NULL,
            PRIMARY KEY (user_id, bgg_id)
        );

        CREATE TABLE IF NOT EXISTS games (
            bgg_id            INTEGER PRIMARY KEY,
            name              TEXT    NOT NULL,
            year_published    INTEGER,
            bgg_rank          INTEGER,
            high_rating_count INTEGER,
            total_raters      INTEGER,
            rating_avg        REAL
        );

        CREATE TABLE IF NOT EXISTS metadata (
            key   TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
    """)
    conn.commit()


def _migrate(conn: sqlite3.Connection) -> None:
    # Migration 1: merge game_stats into games, then drop game_stats
    tables = {row[0] for row in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    )}
    if "game_stats" in tables:
        game_cols = {row[1] for row in conn.execute("PRAGMA table_info(games)")}
        if "high_rating_count" not in game_cols:
            conn.execute("ALTER TABLE games ADD COLUMN high_rating_count INTEGER")
        if "total_raters" not in game_cols:
            conn.execute("ALTER TABLE games ADD COLUMN total_raters INTEGER")
        if "rating_avg" not in game_cols:
            conn.execute("ALTER TABLE games ADD COLUMN rating_avg REAL")
        conn.execute("""
            UPDATE games SET
                high_rating_count = (SELECT high_rating_count FROM game_stats
                                     WHERE game_stats.bgg_id = games.bgg_id),
                total_raters      = (SELECT total_raters      FROM game_stats
                                     WHERE game_stats.bgg_id = games.bgg_id),
                rating_avg        = (SELECT rating_avg        FROM game_stats
                                     WHERE game_stats.bgg_id = games.bgg_id)
            WHERE bgg_id IN (SELECT bgg_id FROM game_stats)
        """)
        conn.execute("DROP TABLE game_stats")
        conn.commit()

    # Migration 2: add stats columns to games if missing (new DB path)
    game_cols = {row[1] for row in conn.execute("PRAGMA table_info(games)")}
    for col, typ in [("high_rating_count", "INTEGER"), ("total_raters", "INTEGER"),
                     ("rating_avg", "REAL")]:
        if col not in game_cols:
            conn.execute(f"ALTER TABLE games ADD COLUMN {col} {typ}")
    conn.commit()

    # Migration 3: add covering index if missing
    indexes = {row[0] for row in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='index'"
    )}
    if "idx_ratings_usr_rtg_bgg" not in indexes:
        print("Building covering index on ratings (one-time, may take a minute)…")
        conn.execute(
            "CREATE INDEX idx_ratings_usr_rtg_bgg ON ratings(user_id, rating, bgg_id)"
        )
        conn.commit()


def create_indexes(conn: sqlite3.Connection) -> None:
    """Create indexes after bulk import. Call once, after import_ratings."""
    conn.executescript("""
        CREATE INDEX IF NOT EXISTS idx_ratings_bgg_id      ON ratings(bgg_id);
        CREATE INDEX IF NOT EXISTS idx_ratings_user_id     ON ratings(user_id);
        CREATE INDEX IF NOT EXISTS idx_ratings_bgg_rtg     ON ratings(bgg_id, rating);
        CREATE INDEX IF NOT EXISTS idx_ratings_usr_rtg_bgg ON ratings(user_id, rating, bgg_id);
    """)
    conn.commit()
