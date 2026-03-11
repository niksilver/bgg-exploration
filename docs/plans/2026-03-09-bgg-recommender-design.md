# BGG Board Game Recommender — Design

**Date:** 2026-03-09
**Last updated:** 2026-03-11

## Overview

A Python CLI tool that takes a list of board games the user likes and returns personalised recommendations using collaborative filtering against a local BGG ratings dataset.

## Architecture

Three layers:

1. **Local SQLite database** — holds imported user ratings and game metadata. Populated once from two Kaggle CSVs; no network access at runtime.
2. **Recommendation engine** — computes item-item collaborative filtering with lift scoring.
3. **CLI entry point** — resolves game names from the local database, runs the engine, prints results.

## Data Sources

Both datasets are downloaded once and imported into SQLite:

- **User ratings:** Kaggle dataset "BoardGameGeek Reviews" (jvanelteren), ~13M ratings by ~290K users.
- **Game metadata:** Kaggle dataset "Board Games Database from BoardGameGeek" (threnjen), ~27K games with names, years, average ratings, and BGG ranks.

Only games present in both datasets are surfaced as recommendations.

## Data Model (SQLite)

```sql
CREATE TABLE ratings (
    user_id  TEXT    NOT NULL,
    bgg_id   INTEGER NOT NULL,
    rating   REAL    NOT NULL,
    PRIMARY KEY (user_id, bgg_id)
);

CREATE TABLE games (
    bgg_id            INTEGER PRIMARY KEY,
    name              TEXT    NOT NULL,
    year_published    INTEGER,
    bgg_rank          INTEGER,
    high_rating_count INTEGER,
    total_raters      INTEGER,
    rating_avg        REAL
);

CREATE TABLE metadata (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
```

The `games` table holds both metadata (name, year, rank — from the game details CSV) and computed stats (high_rating_count, total_raters, rating_avg — computed from the ratings CSV). Each import script updates only its own columns using upsert, so they can be run in any order without overwriting each other's data.

A covering index on `ratings(user_id, rating, bgg_id)` is the key performance optimisation for the recommendation query.

## Recommendation Algorithm

Item-item collaborative filtering with lift:

1. Search the local `games` table to resolve each liked game name to a BGG ID.
2. Find all users who rated any liked game highly (threshold: ≥ 8/10). These are the "fans".
3. Among fans, count how often each other game was also rated highly.
4. Normalise by that game's overall high-rating frequency across all users — this is the **lift**: how much more likely fans of the liked games are to love game X compared with a randomly chosen BGG user.
5. Rank candidates by lift, exclude the liked games themselves, return top N (default 10).

All four steps run as a single SQL query using CTEs.

## CLI Interface

```
python recommend.py "Wingspan" "Terraforming Mars" "Agricola"
python recommend.py "Wingspan" --not expansion --min-avg 7.5 -n 20
```

Options:
- `-n N` / `--top N` — number of results (default 10)
- `--min-avg RATING` — minimum average Kaggle rating (default: no minimum)
- `--not STRING` — exclude games whose name contains STRING (repeatable)

If a game name is ambiguous (substring match returns multiple results), the user is prompted to pick. Entering `Game Name (YYYY)` skips the prompt when the year uniquely identifies the game.

## Error Handling

| Situation | Behaviour |
|-----------|-----------|
| Game name not found in local database | Warn and skip |
| Ratings database missing | Clear message directing user to run the import scripts |

## File Layout

```
bgg-exploration/
  bgg/
    __init__.py
    database.py     # SQLite schema, migrations, open_db
    importer.py     # Kaggle CSV → SQLite bulk import
    recommender.py  # Lift-based collaborative filtering query
  tests/
    __init__.py
    test_database.py
    test_importer.py
    test_recommend.py
    test_recommender.py
  data/
    .gitkeep        # Kaggle CSVs and generated bgg.db go here (gitignored)
  recommend.py      # CLI entry point
  import_ratings.py # One-time ratings import script
  import_games.py   # One-time game metadata import script
  requirements.txt
```

## Testing

- Unit tests for the lift calculation using a small synthetic ratings fixture.
- Unit tests for `import_game_details` and `import_ratings` with temporary CSV files.
- Unit tests for `resolve_game` covering year disambiguation and missing games.
- No tests that hit any external API or network.
