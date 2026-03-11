"""
One-time script to import the Kaggle board games details CSV into the local SQLite database.

Download the dataset from:
  https://www.kaggle.com/datasets/threnjen/board-games-database-from-boardgamegeek

Then run:
  python import_games.py <path-to-games_detailed_info2025.csv>
"""

import sys
from pathlib import Path

from bgg.database import open_db
from bgg.importer import import_game_details

DB_PATH = Path("data/bgg.db")


def main() -> None:
    if len(sys.argv) != 2:
        print("Usage: python import_games.py <path-to-games_detailed_info2025.csv>")
        sys.exit(1)

    csv_path = Path(sys.argv[1])
    if not csv_path.exists():
        print(f"Error: {csv_path} not found")
        sys.exit(1)

    DB_PATH.parent.mkdir(exist_ok=True)
    conn = open_db(DB_PATH)

    print(f"Importing game details from {csv_path}…")
    count = import_game_details(csv_path, conn)
    print(f"Imported {count:,} games.")

    conn.close()
    print(f"Done. Database ready at {DB_PATH}")


if __name__ == "__main__":
    main()
