# Board game recommendations

Get board game recommendations based on games you enjoy.

Examples:
```
python recommend.py "Wingspan" "Terraforming Mars" "Agricola"
python recommend.py "Dominion (2008)"
python recommend.py "Wingspan" --not expansion --min-avg 7.5 -n 20
python recommend.py --help
```

## Setting up

Download both Kaggle datasets and put them in the `data` directory:

1. [BoardGameGeek Reviews](https://www.kaggle.com/datasets/jvanelteren/boardgamegeek-reviews) — user ratings (~13M rows)
2. [Board Games Database from BoardGameGeek](https://www.kaggle.com/datasets/threnjen/board-games-database-from-boardgamegeek) — game metadata (names, years, ranks)

Then import both into the local database:

```
python import_ratings.py data/bgg-26m-reviews.csv
python import_games.py data/games_detailed_info2025.csv
```

The first import takes a few minutes. Only games present in both datasets will appear in recommendations.

## CLI options

| Option | Default | Description |
|--------|---------|-------------|
| `-n N` / `--top N` | 10 | Number of recommendations to show |
| `--min-avg RATING` | 0.0 (off) | Minimum average Kaggle rating for results |
| `--not STRING` | — | Exclude games whose name contains STRING (repeatable) |

## Inspecting the database

```bash
sqlite3 data/bgg.db
```

Useful commands inside the shell:

```sql
.tables                          -- list all tables
.schema game_stats               -- show table definition
.mode column                     -- aligned output
.headers on                      -- show column names

SELECT COUNT(*) FROM ratings;
SELECT COUNT(*) FROM games;
SELECT value FROM metadata WHERE key = 'total_users';

SELECT * FROM game_stats ORDER BY high_rating_count DESC LIMIT 10;
```

Or as a one-liner:

```bash
sqlite3 data/bgg.db "SELECT COUNT(*) FROM ratings;"
```

![Powered by BGG](assets/powered_by_BGG_01_SM.png)
