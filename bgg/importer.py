import csv
import sqlite3
from pathlib import Path

BATCH_SIZE = 10_000


def import_ratings(csv_path: Path, conn: sqlite3.Connection) -> int:
    """Bulk-import ratings from Kaggle CSV. Returns number of valid rows processed."""
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")

    imported = 0
    batch    = []

    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                rating  = float(row["rating"])
                bgg_id  = int(row["ID"])
                user_id = row["user"]
            except (ValueError, KeyError):
                continue
            batch.append((user_id, bgg_id, rating))

            if len(batch) >= BATCH_SIZE:
                conn.executemany(
                    "INSERT OR IGNORE INTO ratings(user_id, bgg_id, rating) VALUES (?, ?, ?)",
                    batch,
                )
                imported += len(batch)
                batch.clear()

    if batch:
        conn.executemany(
            "INSERT OR IGNORE INTO ratings(user_id, bgg_id, rating) VALUES (?, ?, ?)",
            batch,
        )
        imported += len(batch)

    conn.commit()
    return imported


def build_stats(conn: sqlite3.Connection, min_rating: float = 8.0) -> None:
    """Compute game_stats and total_users metadata. Call once after import."""
    conn.execute("""
        INSERT OR REPLACE INTO game_stats (bgg_id, high_rating_count, total_raters)
        SELECT
            bgg_id,
            COUNT(CASE WHEN rating >= ? THEN 1 END),
            COUNT(*)
        FROM ratings
        GROUP BY bgg_id
    """, (min_rating,))

    total_users = conn.execute(
        "SELECT COUNT(DISTINCT user_id) FROM ratings"
    ).fetchone()[0]

    conn.execute(
        "INSERT OR REPLACE INTO metadata(key, value) VALUES ('total_users', ?)",
        (str(total_users),),
    )
    conn.commit()
