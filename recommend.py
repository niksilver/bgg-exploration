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
import textwrap
from dataclasses import dataclass
from pathlib import Path

from bgg.database import open_db
from bgg.recommender import get_recommendations

DB_PATH    = Path("data/bgg.db")
DEFAULT_N  = 10
NAME_W     = 45

COL_ORDER       = ("order", "id", "name", "lift", "rank", "avg", "fanavg")
ALL_COLUMNS     = frozenset(COL_ORDER)
DEFAULT_COLUMNS = frozenset({"order", "name", "rank", "avg", "fanavg"})
COL_WIDTHS      = {"order": 4, "id": 6, "name": NAME_W, "lift": 5,
                   "rank": 6, "avg": 5, "fanavg": 4}
COL_HDRS        = {"order": "#",    "id": "ID",   "name": "Game", "lift": "Lift",
                   "rank": "Rank", "avg": "Avg", "fanavg": "avg"}
COL_ALIGN       = {"order": "<", "id": ">", "name": "<", "lift": ">",
                   "rank": ">", "avg": ">", "fanavg": ">"}


@dataclass(frozen=True)
class GameSearchResult:
    bgg_id: int
    name:   str
    year:   int | None


def _parse_show(value: str, default: frozenset[str]) -> frozenset[str]:
    shown = set(default)
    for token in value.split(","):
        token = token.strip()
        col   = token[1:] if token.startswith("-") else token
        if col not in ALL_COLUMNS:
            raise argparse.ArgumentTypeError(
                f"unknown column '{col}' (valid: {', '.join(COL_ORDER)})"
            )
        if token.startswith("-"):
            shown.discard(col)
        else:
            shown.add(col)
    return frozenset(shown)


def _format_row(
    i:          int,
    name:       str,
    lift:       float,
    bgg_rank:   str,
    avg:        str,
    fan_avg:    str,
    name_width: int = NAME_W,
    bgg_id:     int | None = None,
    shown:      frozenset[str] = DEFAULT_COLUMNS,
) -> str:
    """Format one recommendation row, wrapping long names across multiple lines."""
    pre_parts = []
    if "order" in shown:
        pre_parts.append(f"{i:<4}")
    if "id" in shown:
        assert bgg_id is not None, "bgg_id must be provided when 'id' in shown"
        pre_parts.append(f"{bgg_id:>6}")
    prefix = ("  ".join(pre_parts) + "  ") if pre_parts else ""
    indent = " " * len(prefix)

    stat_parts = []
    if "lift" in shown:
        stat_parts.append(f"{lift:>5.2f}")
    if "rank" in shown:
        stat_parts.append(f"{bgg_rank:>6}")
    if "avg" in shown:
        stat_parts.append(f"{avg:>5}")
    if "fanavg" in shown:
        stat_parts.append(f"{fan_avg:>4}")
    stats = "  ".join(stat_parts)

    if "name" not in shown:
        return (prefix + stats).rstrip()

    lines = textwrap.wrap(name, name_width) or [""]
    if len(lines) == 1:
        return prefix + f"{lines[0]:<{name_width}}  {stats}"
    parts = [prefix + lines[0]]
    for line in lines[1:-1]:
        parts.append(indent + line)
    parts.append(indent + f"{lines[-1]:<{name_width}}  {stats}")
    return "\n".join(parts)


def _search_local(raw_name: str, conn: sqlite3.Connection) -> list[GameSearchResult]:
    """Search the local games table for games whose name contains raw_name."""
    rows = conn.execute(
        "SELECT bgg_id, name, year_published FROM games "
        "WHERE INSTR(LOWER(name), LOWER(?)) > 0 "
        "ORDER BY LENGTH(name) LIMIT 20",
        (raw_name,),
    ).fetchall()
    return [GameSearchResult(bgg_id=r[0], name=r[1], year=r[2]) for r in rows]


def _parse_game_input(raw: str) -> tuple[str, int | None]:
    """Split 'Game Name (Year)' into ('Game Name', year), or return (raw, None)."""
    m = re.match(r'^(.+?)\s*\((\d{4})\)\s*$', raw)
    if m:
        return m.group(1).strip(), int(m.group(2))
    return raw.strip(), None


def resolve_game(
    name: str,
    conn: sqlite3.Connection,
) -> int | None:
    """Search the local database for a game by name. Prompts user to pick if ambiguous."""
    raw_name, year = _parse_game_input(name)
    results = _search_local(raw_name, conn)
    if not results:
        print(f"  Warning: no results for '{raw_name}', skipping.")
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
    parser.add_argument(
        "--id", action="store_true",
        help="Include BGG ID in output",
    )
    parser.add_argument(
        "--lift", action="store_true",
        help="Include Lift column in output",
    )
    args = parser.parse_args()

    if not DB_PATH.exists():
        print(
            "Error: ratings database not found.\n\n"
            "Download the BGG datasets from Kaggle and run:\n"
            "  python import_ratings.py <path-to-bgg-reviews.csv>\n"
            "  python import_games.py <path-to-games_detailed_info2025.csv>\n"
        )
        sys.exit(1)

    conn = open_db(DB_PATH)

    print("Resolving game names…")
    liked_ids: list[int] = []
    for name in args.games:
        bgg_id = resolve_game(name, conn)
        if bgg_id is not None:
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

    stats_w   = (7 if args.lift else 0) + 6 + 2 + 5 + 2 + 4
    id_w      = 8 if args.id else 0
    total_w   = 4 + 2 + id_w + NAME_W + 2 + stats_w
    fan_pad   = total_w - 4
    lift_hdr  = f"  {'Lift':>5}" if args.lift else ""
    id_hdr    = f"  {'ID':>6}"   if args.id   else ""
    print(f"{'':>{fan_pad}}{'Fan':>4}")
    print(f"{'#':<4}{id_hdr}  {'Game':<{NAME_W}}{lift_hdr}  {'Rank':>6}  {'Avg':>5}  {'avg':>4}")
    print("─" * total_w)
    for i, (bgg_id, lift, fan_avg_val) in enumerate(recommendations, 1):
        row = conn.execute(
            "SELECT name, bgg_rank, rating_avg FROM games WHERE bgg_id = ?",
            (bgg_id,),
        ).fetchone()
        name     = row[0] if row else f"BGG ID {bgg_id}"
        bgg_rank = f"#{row[1]}" if row and row[1] else "N/A"
        avg      = f"{row[2]:.2f}" if row and row[2] else "N/A"
        fan_avg  = f"{fan_avg_val:.2f}" if fan_avg_val is not None else "N/A"
        print(_format_row(i, name, lift, bgg_rank, avg, fan_avg,
                          bgg_id=bgg_id, show_id=args.id, show_lift=args.lift))

    conn.close()


if __name__ == "__main__":
    main()
