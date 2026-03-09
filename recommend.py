"""
Board game recommender CLI.

Usage:
  python recommend.py "Wingspan" "Terraforming Mars" "Agricola"
  python recommend.py "Wingspan" -n 5
"""

import argparse
import re
import sqlite3
import sys
from pathlib import Path

from bgg.api import BGGClient
from bgg.database import ensure_game_cached, open_db
from bgg.recommender import get_recommendations

DB_PATH    = Path("data/bgg.db")
DEFAULT_N  = 10


def _parse_game_input(raw: str) -> tuple[str, int | None]:
    """Split 'Game Name (Year)' into ('Game Name', year), or return (raw, None)."""
    m = re.match(r'^(.+?)\s*\((\d{4})\)\s*$', raw)
    if m:
        return m.group(1).strip(), int(m.group(2))
    return raw.strip(), None


def resolve_game(
    name:   str,
    client: BGGClient,
    conn:   sqlite3.Connection,
) -> int | None:
    """Search BGG for a game by name. Prompts user to pick if ambiguous."""
    raw_name, year = _parse_game_input(name)
    results = client.search(raw_name)
    if not results:
        print(f"  Warning: no BGG results for '{raw_name}', skipping.")
        return None

    exact      = [r for r in results if r.name.lower() == raw_name.lower()]
    candidates = exact or results

    if year is not None:
        year_match = [r for r in candidates if r.year == year]
        if len(year_match) == 1:
            return year_match[0].bgg_id
        if year_match:
            candidates = year_match   # still ambiguous but narrowed by year
    elif len(exact) == 1:
        return exact[0].bgg_id

    candidates = candidates[:5]
    print(f"\nMultiple results for '{raw_name}':")
    for i, r in enumerate(candidates, 1):
        yr = f" ({r.year})" if r.year else ""
        print(f"  {i}. {r.name}{yr}  [BGG ID {r.bgg_id}]")
    print("  0. Skip")

    while True:
        try:
            choice = int(input("Enter number: ").strip())
        except EOFError:
            return None
        except ValueError:
            continue
        if choice == 0:
            return None
        if 1 <= choice <= len(candidates):
            return candidates[choice - 1].bgg_id


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Recommend board games based on games you enjoy."
    )
    parser.add_argument(
        "games", nargs="+", metavar="GAME",
        help="Board games you like (quote multi-word titles)",
    )
    parser.add_argument(
        "-n", "--top", type=int, default=DEFAULT_N,
        metavar="N", help=f"Number of recommendations (default {DEFAULT_N})",
    )
    parser.add_argument(
        "--min-avg", type=float, default=0.0,
        metavar="RATING",
        help="Minimum BGG average rating for recommended games (default: no minimum)",
    )
    parser.add_argument(
        "--not", dest="exclusions", action="append", default=[], metavar="STRING",
        help="Exclude games whose name contains STRING (case-insensitive, repeatable)",
    )
    args = parser.parse_args()

    if not DB_PATH.exists():
        print(
            "Error: ratings database not found.\n\n"
            "Download the BGG Reviews dataset from:\n"
            "  https://www.kaggle.com/datasets/jvanelteren/boardgamegeek-reviews\n\n"
            "Then run:\n"
            "  python import_ratings.py <path-to-csv>\n"
        )
        sys.exit(1)

    conn   = open_db(DB_PATH)
    client = BGGClient()

    print("Powered by BGG")
    print("Resolving game names via BGG API…")
    liked_ids: list[int] = []
    for name in args.games:
        bgg_id = resolve_game(name, client, conn)
        if bgg_id is not None:
            ensure_game_cached(bgg_id, client, conn)
            liked_ids.append(bgg_id)

    if not liked_ids:
        print("No valid games to base recommendations on. Exiting.")
        sys.exit(1)

    liked_names = {
        row[0]: row[1]
        for row in conn.execute(
            f"SELECT bgg_id, name FROM games WHERE bgg_id IN "
            f"({','.join('?'*len(liked_ids))})",
            liked_ids,
        )
    }
    print(f"\nRecommendations based on: {', '.join(liked_names.values())}\n")

    recommendations = get_recommendations(
        liked_ids, conn, top_n=args.top, min_avg=args.min_avg,
        exclusions=args.exclusions,
    )
    if not recommendations:
        print("No recommendations found. Try adding more liked games.")
        conn.close()
        sys.exit(0)

    print(f"{'#':<4}  {'Game':<45}  {'Lift':>5}  {'Rank':>6}  {'Avg':>5}")
    print("─" * 73)
    for i, (bgg_id, lift) in enumerate(recommendations, 1):
        ensure_game_cached(bgg_id, client, conn)
        row = conn.execute(
            "SELECT name, bgg_rank, rating_avg FROM games WHERE bgg_id = ?",
            (bgg_id,),
        ).fetchone()
        name     = row[0] if row else f"BGG ID {bgg_id}"
        bgg_rank = f"#{row[1]}" if row and row[1] else "N/A"
        avg      = f"{row[2]:.2f}" if row and row[2] else "N/A"
        print(f"{i:<4}  {name:<45}  {lift:>5.2f}  {bgg_rank:>6}  {avg:>5}")

    conn.close()


if __name__ == "__main__":
    main()
