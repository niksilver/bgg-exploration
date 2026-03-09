# Board game recommendations

Get board game recommendations, thanks to Board Game Geek.

Examples:
```
python recommend.py "Wingspan" "Terraforming Mars" "Agricola"
python recommend.py --help
```

## Setting up

- Download the
  [Kaggle dataset by jvanelteren](https://www.kaggle.com/datasets/jvanelteren/boardgamegeek-reviews/)
  and put it into the `data` directory.
- Run `python import_ratings.py data/name-of-dataset/csv`.
- Get a BGG token and put into `data/token.json` like this:
```
{
    "name": "Recommendation1",
    "value": "0495-my-token-here-etc-af56e"
}
```

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
SELECT COUNT(*) FROM game_stats;
SELECT value FROM metadata WHERE key = 'total_users';

SELECT * FROM game_stats ORDER BY high_rating_count DESC LIMIT 10;
```

Or as a one-liner:

```bash
sqlite3 data/bgg.db "SELECT COUNT(*) FROM ratings;"
```

[Powered by BGG](https://drive.google.com/file/d/1unpb690BONNJB5HXtJEHfO4Raz7I-5JO/view?usp=drive_link)
