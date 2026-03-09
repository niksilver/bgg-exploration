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

        CREATE TABLE IF NOT EXISTS game_stats (
            bgg_id            INTEGER PRIMARY KEY,
            high_rating_count INTEGER NOT NULL,
            total_raters      INTEGER NOT NULL,
            rating_avg        REAL
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


def _migrate(conn: sqlite3.Connection) -> None:
    cols = {row[1] for row in conn.execute("PRAGMA table_info(game_stats)")}
    if "rating_avg" not in cols:
        conn.execute("ALTER TABLE game_stats ADD COLUMN rating_avg REAL")
        conn.commit()


def create_indexes(conn: sqlite3.Connection) -> None:
    """Create indexes after bulk import. Call once, after import_ratings."""
    conn.executescript("""
        CREATE INDEX IF NOT EXISTS idx_ratings_bgg_id  ON ratings(bgg_id);
        CREATE INDEX IF NOT EXISTS idx_ratings_user_id ON ratings(user_id);
        CREATE INDEX IF NOT EXISTS idx_ratings_bgg_rtg ON ratings(bgg_id, rating);
    """)
    conn.commit()


def ensure_game_cached(
    bgg_id: int,
    client,          # BGGClient — not type-hinted to avoid circular import
    conn: sqlite3.Connection,
) -> None:
    """Fetch game details from BGG API and cache in `games` table if not already present."""
    exists = conn.execute(
        "SELECT 1 FROM games WHERE bgg_id = ?", (bgg_id,)
    ).fetchone()
    if exists:
        return

    details = client.fetch(bgg_id)
    if details is None:
        return

    conn.execute(
        """INSERT OR REPLACE INTO games
               (bgg_id, name, year_published, rating_avg, bgg_rank)
           VALUES (?, ?, ?, ?, ?)""",
        (details.bgg_id, details.name, details.year,
         details.rating_avg, details.bgg_rank),
    )
    conn.commit()
