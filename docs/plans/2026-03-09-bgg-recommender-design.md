# BGG Board Game Recommender — Design

**Date:** 2026-03-09

## Overview

A Python CLI tool that takes a list of board games the user likes and returns personalised recommendations using collaborative filtering against a local BGG ratings dataset.

## Architecture

Four layers:

1. **BGG API client** — wraps the BGG XML API v2. Handles game search by name, fetch by ID, rate limiting, and XML parsing.
2. **Local SQLite database** — caches game metadata and holds the imported user ratings.
3. **Recommendation engine** — computes item-item collaborative filtering with lift scoring.
4. **CLI entry point** — resolves game names, runs the engine, prints results.

## Data Sources

- **User ratings:** Kaggle dataset "BoardGameGeek Reviews" (jvanelteren), ~13M ratings by ~290K users. Downloaded once and imported into SQLite.
- **Game metadata:** BGG XML API v2, fetched on demand and cached locally.

## Data Model (SQLite)

```sql
CREATE TABLE ratings (
    user_id  TEXT,
    bgg_id   INTEGER,
    rating   REAL
);

CREATE TABLE games (
    bgg_id          INTEGER PRIMARY KEY,
    name            TEXT,
    year_published  INTEGER
);
```

`ratings` is bulk-loaded from the Kaggle CSV at setup time. `games` is populated on demand via the BGG API when resolving user-typed names to IDs.

## Recommendation Algorithm

Item-item collaborative filtering with lift:

1. Resolve each liked game name → BGG ID via BGG search API (cache in `games` table).
2. Find all users who rated any liked game highly (threshold: ≥ 8/10).
3. Among those users, count how often each other game was also rated highly.
4. Normalise by that game's overall high-rating frequency across all users (lift = how much more likely fans of your games are to like game X vs. the average BGG user).
5. Rank candidates by lift, exclude the liked games themselves, return top N (default 10).

## CLI Interface

```
python recommend.py "Wingspan" "Terraforming Mars" "Agricola"
```

- If a game name matches multiple BGG entries, prompt the user to disambiguate.
- Print top 10 recommendations with BGG rank and average rating.

## Error Handling

| Situation | Behaviour |
|-----------|-----------|
| Game name not found on BGG | Warn and skip |
| Ratings database missing | Clear message directing user to download the Kaggle dataset |
| BGG API rate limit / network error | Retry with exponential backoff, then fail gracefully |

## Testing

- Unit tests for the lift calculation using a small synthetic ratings fixture.
- Integration tests for the BGG API client with mocked HTTP responses.
- No tests that hit the live BGG API.
