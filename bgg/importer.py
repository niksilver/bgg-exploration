import csv
import sqlite3
import time
from datetime import datetime
from pathlib import Path

BATCH_SIZE        = 10_000
PROGRESS_INTERVAL = 1.0  # seconds


def import_ratings(csv_path: Path, conn: sqlite3.Connection) -> int:
    """Bulk-import ratings from Kaggle CSV. Returns number of valid rows processed."""
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")

    imported      = 0
    batch         = []
    game_names:   dict[int, str] = {}
    last_progress = time.monotonic()

    with open(csv_path, newline="", encoding="utf-8") as f:
        reader    = csv.DictReader(f)
        fieldnames = reader.fieldnames or []
        required  = {"user", "ID", "rating"}
        missing   = required - set(fieldnames)
        if missing:
            raise ValueError(
                f"CSV is missing required columns: {sorted(missing)}. "
                f"Expected columns: {sorted(required)}. "
                f"Found: {sorted(fieldnames)}."
            )
        has_name = "name" in fieldnames
        for row in reader:
            try:
                rating  = float(row["rating"])
                bgg_id  = int(row["ID"])
                user_id = row["user"]
            except (ValueError, KeyError):
                continue

            if has_name and bgg_id not in game_names and row["name"]:
                game_names[bgg_id] = row["name"]

            batch.append((user_id, bgg_id, rating))
            imported += 1

            now = time.monotonic()
            if now - last_progress >= PROGRESS_INTERVAL:
                ts = datetime.now().strftime("%H:%M:%S")
                print(f"[{ts}] {imported:,} records processed")
                last_progress = now

            if len(batch) >= BATCH_SIZE:
                conn.executemany(
                    "INSERT OR IGNORE INTO ratings(user_id, bgg_id, rating) VALUES (?, ?, ?)",
                    batch,
                )
                batch.clear()

    if batch:
        conn.executemany(
            "INSERT OR IGNORE INTO ratings(user_id, bgg_id, rating) VALUES (?, ?, ?)",
            batch,
        )

    if game_names:
        conn.executemany(
            "INSERT OR IGNORE INTO games(bgg_id, name) VALUES (?, ?)",
            game_names.items(),
        )

    conn.commit()
    return imported


def import_game_details(csv_path: Path, conn: sqlite3.Connection) -> int:
    """Import game metadata from games_detailed_info2025.csv. Returns number of rows imported."""
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader    = csv.DictReader(f)
        fieldnames = reader.fieldnames or []
        required  = {"id", "name", "yearpublished", "average", "Board Game Rank"}
        missing   = required - set(fieldnames)
        if missing:
            raise ValueError(
                f"CSV is missing required columns: {sorted(missing)}. "
                f"Found: {sorted(fieldnames)}."
            )

        batch = []
        for row in reader:
            try:
                bgg_id         = int(row["id"])
                name           = row["name"].strip()
                year_published = int(row["yearpublished"]) if row["yearpublished"].strip() else None
                rating_avg     = float(row["average"])    if row["average"].strip()       else None
                rank_str       = row["Board Game Rank"].strip()
                bgg_rank       = int(rank_str) if rank_str.isdigit() else None
            except (ValueError, KeyError):
                continue
            batch.append((bgg_id, name, year_published, rating_avg, bgg_rank))

    conn.executemany(
        """INSERT OR REPLACE INTO games(bgg_id, name, year_published, rating_avg, bgg_rank)
           VALUES (?, ?, ?, ?, ?)""",
        batch,
    )
    conn.commit()
    return len(batch)


def build_stats(conn: sqlite3.Connection, min_rating: float = 8.0) -> None:
    """Compute game_stats and total_users metadata. Call once after import."""
    conn.execute("""
        INSERT OR REPLACE INTO game_stats (bgg_id, high_rating_count, total_raters, rating_avg)
        SELECT
            bgg_id,
            COUNT(CASE WHEN rating >= ? THEN 1 END),
            COUNT(*),
            AVG(rating)
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
