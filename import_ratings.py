"""
One-time script to import the Kaggle BGG Reviews CSV into a local SQLite database.

Download the dataset from:
  https://www.kaggle.com/datasets/jvanelteren/boardgamegeek-reviews

Then run:
  python import_ratings.py <path-to-bgg-reviews.csv>
"""

import sys
from pathlib import Path

from bgg.database import open_db, create_indexes
from bgg.importer import build_stats, import_ratings

DB_PATH = Path("data/bgg.db")


def main() -> None:
    if len(sys.argv) != 2:
        print("Usage: python import_ratings.py <path-to-ratings.csv>")
        sys.exit(1)

    csv_path = Path(sys.argv[1])
    if not csv_path.exists():
        print(f"Error: {csv_path} not found")
        sys.exit(1)

    DB_PATH.parent.mkdir(exist_ok=True)
    conn = open_db(DB_PATH)

    print(f"Importing ratings from {csv_path}…")
    count = import_ratings(csv_path, conn)
    print(f"Imported {count:,} ratings.")

    print("Building indexes (this may take a minute)…")
    create_indexes(conn)

    print("Computing game statistics…")
    build_stats(conn)

    conn.close()
    print(f"Done. Database ready at {DB_PATH}")


if __name__ == "__main__":
    main()
