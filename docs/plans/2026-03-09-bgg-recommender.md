# BGG Board Game Recommender — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** A Python CLI tool that takes board game names the user likes and returns personalised recommendations using item-item collaborative filtering with lift, backed by a local SQLite database seeded from the Kaggle BGG Reviews dataset.

**Architecture:** The user runs `python recommend.py "Wingspan" "Agricola"`. The app resolves names to BGG IDs via the BGG XML API v2, then queries a local SQLite database of ~13M user ratings (imported once from Kaggle) to compute lift scores — how much more likely fans of the liked games are to also like each candidate game. A separate `import_ratings.py` script handles the one-time Kaggle CSV import.

**Tech Stack:** Python 3.11+, `requests` (BGG API), `sqlite3` stdlib (local DB), `pytest` + `unittest.mock` (tests), no external ML libraries.

---

## File Layout

```
bgg-exploration/
  bgg/
    __init__.py
    api.py          # BGG XML API v2 client
    database.py     # SQLite schema + ensure_game_cached helper
    importer.py     # Kaggle CSV → SQLite bulk import
    recommender.py  # Lift-based collaborative filtering query
  tests/
    __init__.py
    test_api.py
    test_importer.py
    test_recommender.py
  data/
    .gitkeep        # Kaggle CSV and generated bgg.db go here (gitignored)
  recommend.py      # CLI entry point
  import_ratings.py # One-time import script
  requirements.txt
```

---

### Task 1: Project scaffold and dependencies

**Files:**
- Create: `requirements.txt`
- Create: `bgg/__init__.py`
- Create: `tests/__init__.py`
- Create: `data/.gitkeep`
- Modify: `.gitignore`

**Step 1: Create `requirements.txt`**

```
requests>=2.31.0
pytest>=7.4.0
```

**Step 2: Create package and test directories**

```bash
mkdir -p bgg tests data
touch bgg/__init__.py tests/__init__.py data/.gitkeep
```

**Step 3: Create/update `.gitignore`**

Add these lines to `.gitignore` (create it if it doesn't exist):

```
data/*.csv
data/*.db
__pycache__/
*.pyc
.pytest_cache/
```

**Step 4: Install dependencies**

```bash
pip install -r requirements.txt
```

Expected: installs `requests` and `pytest` without errors.

**Step 5: Verify pytest runs**

```bash
pytest tests/ -v
```

Expected: `no tests ran` (0 collected).

**Step 6: Commit**

```bash
git add bgg/ tests/ data/.gitkeep requirements.txt .gitignore
git commit -m "feat: scaffold project structure"
```

---

### Task 2: Database schema

**Files:**
- Create: `bgg/database.py`
- Create: `tests/test_database.py`

**Step 1: Write the failing test**

Create `tests/test_database.py`:

```python
import sqlite3
import pytest
from bgg.database import open_db


def test_open_db_creates_tables(tmp_path):
    db_path = tmp_path / "test.db"
    conn = open_db(db_path)

    tables = {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
    }
    assert tables == {"ratings", "game_stats", "games", "metadata"}
    conn.close()


def test_open_db_is_idempotent(tmp_path):
    db_path = tmp_path / "test.db"
    conn1 = open_db(db_path)
    conn1.close()
    conn2 = open_db(db_path)  # must not raise
    conn2.close()
```

**Step 2: Run to verify it fails**

```bash
pytest tests/test_database.py -v
```

Expected: `ImportError` — `bgg.database` doesn't exist yet.

**Step 3: Implement `bgg/database.py`**

```python
import sqlite3
from pathlib import Path


def open_db(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA foreign_keys = ON")
    _create_tables(conn)
    return conn


def _create_tables(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS ratings (
            user_id  TEXT    NOT NULL,
            bgg_id   INTEGER NOT NULL,
            rating   REAL    NOT NULL
        );

        CREATE TABLE IF NOT EXISTS game_stats (
            bgg_id            INTEGER PRIMARY KEY,
            high_rating_count INTEGER NOT NULL,
            total_raters      INTEGER NOT NULL
        );

        CREATE TABLE IF NOT EXISTS games (
            bgg_id         INTEGER PRIMARY KEY,
            name           TEXT    NOT NULL,
            year_published INTEGER,
            rating_avg     REAL,
            bgg_rank       INTEGER
        );

        CREATE TABLE IF NOT EXISTS metadata (
            key   TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
    """)
    conn.commit()


def create_indexes(conn: sqlite3.Connection) -> None:
    """Create indexes after bulk import. Call once, after import_ratings."""
    conn.executescript("""
        CREATE INDEX IF NOT EXISTS idx_ratings_bgg_id  ON ratings(bgg_id);
        CREATE INDEX IF NOT EXISTS idx_ratings_user_id ON ratings(user_id);
        CREATE INDEX IF NOT EXISTS idx_ratings_bgg_rtg ON ratings(bgg_id, rating);
    """)
    conn.commit()
```

**Step 4: Run tests to verify they pass**

```bash
pytest tests/test_database.py -v
```

Expected: 2 passed.

**Step 5: Commit**

```bash
git add bgg/database.py tests/test_database.py
git commit -m "feat: add SQLite schema and open_db helper"
```

---

### Task 3: BGG XML API client

**Files:**
- Create: `bgg/api.py`
- Create: `tests/test_api.py`

**Step 1: Write the failing tests**

Create `tests/test_api.py`:

```python
from unittest.mock import MagicMock, patch
from bgg.api import BGGClient, GameSearchResult, GameDetails

SEARCH_XML = """<?xml version="1.0" encoding="utf-8"?>
<items total="2">
    <item type="boardgame" id="266192">
        <name type="primary" sortindex="1" value="Wingspan"/>
        <yearpublished value="2019"/>
    </item>
    <item type="boardgame" id="293260">
        <name type="primary" sortindex="1" value="Wingspan: European Expansion"/>
        <yearpublished value="2019"/>
    </item>
</items>"""

FETCH_XML = """<?xml version="1.0" encoding="utf-8"?>
<items>
    <item type="boardgame" id="266192">
        <name type="primary" sortindex="1" value="Wingspan"/>
        <yearpublished value="2019"/>
        <statistics page="1">
            <ratings>
                <average value="8.07"/>
                <ranks>
                    <rank type="subtype" id="1" name="boardgame"
                          friendlyname="Board Game Rank" value="21"
                          bayesaverage="8.01"/>
                </ranks>
            </ratings>
        </statistics>
    </item>
</items>"""

EMPTY_XML = """<?xml version="1.0" encoding="utf-8"?>
<items total="0"/>"""


def _mock_response(text: str, status: int = 200) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status
    resp.text = text
    return resp


def test_search_returns_results():
    session = MagicMock()
    session.get.return_value = _mock_response(SEARCH_XML)
    client = BGGClient(session=session)

    results = client.search("Wingspan")

    assert len(results) == 2
    assert results[0] == GameSearchResult(bgg_id=266192, name="Wingspan", year=2019)
    assert results[1].bgg_id == 293260


def test_search_returns_empty_list_when_no_results():
    session = MagicMock()
    session.get.return_value = _mock_response(EMPTY_XML)
    client = BGGClient(session=session)

    results = client.search("xyzzy")

    assert results == []


def test_fetch_returns_game_details():
    session = MagicMock()
    session.get.return_value = _mock_response(FETCH_XML)
    client = BGGClient(session=session)

    details = client.fetch(266192)

    assert details == GameDetails(
        bgg_id=266192, name="Wingspan", year=2019,
        rating_avg=8.07, bgg_rank=21,
    )


def test_fetch_returns_none_when_item_missing():
    session = MagicMock()
    session.get.return_value = _mock_response(EMPTY_XML)
    client = BGGClient(session=session)

    assert client.fetch(999999) is None
```

**Step 2: Run to verify they fail**

```bash
pytest tests/test_api.py -v
```

Expected: `ImportError` — `bgg.api` doesn't exist yet.

**Step 3: Implement `bgg/api.py`**

```python
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass

import requests

BGG_API_BASE    = "https://boardgamegeek.com/xmlapi2"
RATE_LIMIT_SECS = 2.0


@dataclass(frozen=True)
class GameSearchResult:
    bgg_id: int
    name:   str
    year:   int | None


@dataclass(frozen=True)
class GameDetails:
    bgg_id:     int
    name:       str
    year:       int | None
    rating_avg: float | None
    bgg_rank:   int | None


class BGGClient:
    def __init__(self, session: requests.Session | None = None):
        self._session      = session or requests.Session()
        self._last_request = 0.0

    def _get(self, endpoint: str, params: dict) -> ET.Element:
        elapsed = time.monotonic() - self._last_request
        if elapsed < RATE_LIMIT_SECS:
            time.sleep(RATE_LIMIT_SECS - elapsed)

        url = f"{BGG_API_BASE}/{endpoint}"
        for attempt in range(3):
            resp = self._session.get(url, params=params, timeout=10)
            if resp.status_code == 200:
                self._last_request = time.monotonic()
                return ET.fromstring(resp.text)
            if resp.status_code == 429:
                time.sleep(5 * (attempt + 1))
            else:
                resp.raise_for_status()

        raise RuntimeError(f"BGG API failed after 3 attempts: {url}")

    def search(self, query: str) -> list[GameSearchResult]:
        root = self._get("search", {"query": query, "type": "boardgame"})
        results = []
        for item in root.findall("item"):
            bgg_id   = int(item.get("id"))
            name_el  = item.find("name[@type='primary']")
            name     = name_el.get("value") if name_el is not None else "Unknown"
            year_el  = item.find("yearpublished")
            year     = int(year_el.get("value")) if year_el is not None else None
            results.append(GameSearchResult(bgg_id=bgg_id, name=name, year=year))
        return results

    def fetch(self, bgg_id: int) -> GameDetails | None:
        root = self._get("thing", {"id": bgg_id, "type": "boardgame", "stats": 1})
        item = root.find("item")
        if item is None:
            return None

        name_el = item.find("name[@type='primary']")
        name    = name_el.get("value") if name_el is not None else "Unknown"
        year_el = item.find("yearpublished")
        year    = int(year_el.get("value")) if year_el is not None else None

        rating_avg = None
        avg_el = item.find(".//average")
        if avg_el is not None:
            try:
                rating_avg = float(avg_el.get("value"))
            except (ValueError, TypeError):
                pass

        bgg_rank = None
        rank_el = item.find(".//rank[@name='boardgame']")
        if rank_el is not None:
            try:
                bgg_rank = int(rank_el.get("value"))
            except (ValueError, TypeError):
                pass

        return GameDetails(
            bgg_id=bgg_id, name=name, year=year,
            rating_avg=rating_avg, bgg_rank=bgg_rank,
        )
```

**Step 4: Run tests to verify they pass**

```bash
pytest tests/test_api.py -v
```

Expected: 4 passed.

**Step 5: Commit**

```bash
git add bgg/api.py tests/test_api.py
git commit -m "feat: add BGG XML API v2 client with search and fetch"
```

---

### Task 4: `ensure_game_cached` helper

This helper fetches a game from the BGG API and stores it in the `games` table, skipping the API call if already cached.

**Files:**
- Modify: `bgg/database.py`
- Modify: `tests/test_database.py`

**Step 1: Write the failing test**

Append to `tests/test_database.py`:

```python
from unittest.mock import MagicMock
from bgg.api import GameDetails
from bgg.database import ensure_game_cached


def test_ensure_game_cached_inserts_on_first_call(tmp_path):
    conn = open_db(tmp_path / "test.db")
    details = GameDetails(bgg_id=266192, name="Wingspan", year=2019,
                          rating_avg=8.07, bgg_rank=21)
    client = MagicMock()
    client.fetch.return_value = details

    ensure_game_cached(266192, client, conn)

    row = conn.execute(
        "SELECT name, year_published, rating_avg, bgg_rank FROM games WHERE bgg_id=?",
        (266192,),
    ).fetchone()
    assert row == ("Wingspan", 2019, 8.07, 21)
    client.fetch.assert_called_once_with(266192)


def test_ensure_game_cached_skips_api_if_already_present(tmp_path):
    conn = open_db(tmp_path / "test.db")
    conn.execute(
        "INSERT INTO games(bgg_id, name) VALUES (?, ?)", (266192, "Wingspan")
    )
    conn.commit()
    client = MagicMock()

    ensure_game_cached(266192, client, conn)

    client.fetch.assert_not_called()
```

**Step 2: Run to verify they fail**

```bash
pytest tests/test_database.py -v
```

Expected: 2 new failures — `ensure_game_cached` not imported.

**Step 3: Add `ensure_game_cached` to `bgg/database.py`**

Add this function at the bottom of `bgg/database.py` (after `create_indexes`):

```python
def ensure_game_cached(
    bgg_id: int,
    client,          # BGGClient — not type-hinted to avoid circular import
    conn: sqlite3.Connection,
) -> None:
    """Fetch game details from BGG API and cache in `games` table if not already present."""
    exists = conn.execute(
        "SELECT 1 FROM games WHERE bgg_id = ?", (bgg_id,)
    ).fetchone()
    if exists:
        return

    details = client.fetch(bgg_id)
    if details is None:
        return

    conn.execute(
        """INSERT OR REPLACE INTO games
               (bgg_id, name, year_published, rating_avg, bgg_rank)
           VALUES (?, ?, ?, ?, ?)""",
        (details.bgg_id, details.name, details.year,
         details.rating_avg, details.bgg_rank),
    )
    conn.commit()
```

**Step 4: Run all tests to verify they pass**

```bash
pytest tests/ -v
```

Expected: all pass (no regressions).

**Step 5: Commit**

```bash
git add bgg/database.py tests/test_database.py
git commit -m "feat: add ensure_game_cached helper"
```

---

### Task 5: Kaggle CSV importer

**Files:**
- Create: `bgg/importer.py`
- Create: `tests/test_importer.py`

The Kaggle "BoardGameGeek Reviews" CSV (`bgg-13m-reviews.csv`) has columns: `user`, `ID`, `name`, `rating`. Ratings of `"N/A"` or non-numeric values must be skipped.

**Step 1: Write the failing tests**

Create `tests/test_importer.py`:

```python
import csv
import pytest
from bgg.database import open_db
from bgg.importer import import_ratings, build_stats


def _write_csv(path, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["user", "ID", "name", "rating"])
        writer.writeheader()
        writer.writerows(rows)


def test_import_ratings_counts_valid_rows(tmp_path):
    csv_path = tmp_path / "ratings.csv"
    _write_csv(csv_path, [
        {"user": "alice", "ID": "1",  "name": "Wingspan",         "rating": "9"},
        {"user": "alice", "ID": "2",  "name": "Agricola",         "rating": "8"},
        {"user": "bob",   "ID": "1",  "name": "Wingspan",         "rating": "N/A"},
        {"user": "bob",   "ID": "3",  "name": "Terraforming Mars","rating": "7"},
    ])
    conn = open_db(tmp_path / "test.db")

    count = import_ratings(csv_path, conn)

    assert count == 3  # N/A row skipped


def test_import_ratings_skips_non_numeric(tmp_path):
    csv_path = tmp_path / "ratings.csv"
    _write_csv(csv_path, [
        {"user": "alice", "ID": "1", "name": "Wingspan", "rating": "N/A"},
        {"user": "alice", "ID": "2", "name": "Agricola", "rating": "bad"},
    ])
    conn = open_db(tmp_path / "test.db")

    count = import_ratings(csv_path, conn)

    assert count == 0


def test_build_stats_computes_high_rating_count(tmp_path):
    csv_path = tmp_path / "ratings.csv"
    _write_csv(csv_path, [
        {"user": "alice", "ID": "1", "name": "Wingspan", "rating": "9"},
        {"user": "bob",   "ID": "1", "name": "Wingspan", "rating": "8"},
        {"user": "carol", "ID": "1", "name": "Wingspan", "rating": "5"},
        {"user": "dave",  "ID": "2", "name": "Agricola", "rating": "9"},
    ])
    conn = open_db(tmp_path / "test.db")
    import_ratings(csv_path, conn)

    build_stats(conn, min_rating=8.0)

    row = conn.execute(
        "SELECT high_rating_count, total_raters FROM game_stats WHERE bgg_id=1"
    ).fetchone()
    assert row == (2, 3)  # alice+bob >= 8; carol < 8

    total_users = conn.execute(
        "SELECT value FROM metadata WHERE key='total_users'"
    ).fetchone()[0]
    assert total_users == "4"
```

**Step 2: Run to verify they fail**

```bash
pytest tests/test_importer.py -v
```

Expected: `ImportError` — `bgg.importer` doesn't exist.

**Step 3: Implement `bgg/importer.py`**

```python
import csv
import sqlite3
from pathlib import Path

BATCH_SIZE = 10_000


def import_ratings(csv_path: Path, conn: sqlite3.Connection) -> int:
    """Bulk-import ratings from Kaggle CSV. Returns number of rows imported."""
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")

    imported = 0
    batch    = []

    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                rating = float(row["rating"])
            except (ValueError, KeyError):
                continue

            bgg_id  = int(row["ID"])
            user_id = row["user"]
            batch.append((user_id, bgg_id, rating))

            if len(batch) >= BATCH_SIZE:
                conn.executemany(
                    "INSERT INTO ratings(user_id, bgg_id, rating) VALUES (?, ?, ?)",
                    batch,
                )
                imported += len(batch)
                batch.clear()

    if batch:
        conn.executemany(
            "INSERT INTO ratings(user_id, bgg_id, rating) VALUES (?, ?, ?)",
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
```

**Step 4: Run all tests**

```bash
pytest tests/ -v
```

Expected: all pass.

**Step 5: Commit**

```bash
git add bgg/importer.py tests/test_importer.py
git commit -m "feat: add Kaggle CSV importer and game_stats builder"
```

---

### Task 6: Recommendation engine

**Files:**
- Create: `bgg/recommender.py`
- Create: `tests/test_recommender.py`

**Step 1: Write the failing tests**

Create `tests/test_recommender.py`:

```python
import pytest
from bgg.database import open_db
from bgg.recommender import get_recommendations


def _seed(conn, ratings):
    """Insert (user_id, bgg_id, rating) tuples and build stats."""
    conn.executemany(
        "INSERT INTO ratings(user_id, bgg_id, rating) VALUES (?, ?, ?)", ratings
    )
    conn.commit()
    # Build stats with threshold 8.0
    conn.execute("""
        INSERT OR REPLACE INTO game_stats (bgg_id, high_rating_count, total_raters)
        SELECT bgg_id,
               COUNT(CASE WHEN rating >= 8.0 THEN 1 END),
               COUNT(*)
        FROM ratings GROUP BY bgg_id
    """)
    total = conn.execute(
        "SELECT COUNT(DISTINCT user_id) FROM ratings"
    ).fetchone()[0]
    conn.execute(
        "INSERT OR REPLACE INTO metadata(key, value) VALUES ('total_users', ?)",
        (str(total),),
    )
    conn.commit()


def test_recommends_game_with_high_lift(tmp_path):
    conn = open_db(tmp_path / "test.db")
    # 10 users love both game 1 and game 2.
    # Only 1 user (who doesn't like game 1) loves game 3.
    # Lift for game 2 should be much higher than for game 3.
    ratings = (
        [(f"u{i}", 1, 9.0) for i in range(10)] +   # 10 fans of game 1
        [(f"u{i}", 2, 9.0) for i in range(10)] +   # same 10 also love game 2
        [("u99", 3, 9.0)]                           # unrelated user loves game 3
    )
    _seed(conn, ratings)

    results = get_recommendations([1], conn, min_rating=8.0, min_fan_count=1)

    bgg_ids = [r[0] for r in results]
    assert bgg_ids[0] == 2            # game 2 should rank first
    assert 3 in bgg_ids               # game 3 should appear but lower


def test_liked_games_excluded_from_results(tmp_path):
    conn = open_db(tmp_path / "test.db")
    ratings = (
        [("u1", 1, 9.0), ("u1", 2, 9.0)] +
        [("u2", 1, 9.0), ("u2", 2, 9.0)]
    )
    _seed(conn, ratings)

    results = get_recommendations([1, 2], conn, min_rating=8.0, min_fan_count=1)

    bgg_ids = [r[0] for r in results]
    assert 1 not in bgg_ids
    assert 2 not in bgg_ids


def test_returns_empty_for_empty_input(tmp_path):
    conn = open_db(tmp_path / "test.db")
    assert get_recommendations([], conn) == []


def test_min_fan_count_filters_obscure_games(tmp_path):
    conn = open_db(tmp_path / "test.db")
    ratings = (
        [(f"u{i}", 1, 9.0) for i in range(10)] +   # 10 fans of game 1
        [(f"u{i}", 2, 9.0) for i in range(10)] +   # all 10 also like game 2
        [("u0", 3, 9.0)]                            # only 1 fan-user likes game 3
    )
    _seed(conn, ratings)

    results = get_recommendations([1], conn, min_rating=8.0, min_fan_count=5)

    bgg_ids = [r[0] for r in results]
    assert 2 in bgg_ids
    assert 3 not in bgg_ids   # filtered out: only 1 fan-user, below threshold
```

**Step 2: Run to verify they fail**

```bash
pytest tests/test_recommender.py -v
```

Expected: `ImportError` — `bgg.recommender` doesn't exist.

**Step 3: Implement `bgg/recommender.py`**

```python
import sqlite3


def get_recommendations(
    liked_bgg_ids: list[int],
    conn:          sqlite3.Connection,
    min_rating:    float = 8.0,
    min_fan_count: int   = 5,
    top_n:         int   = 10,
) -> list[tuple[int, float]]:
    """
    Return (bgg_id, lift) pairs sorted by lift descending.

    Lift = (fraction of fans who highly rated the game) /
           (fraction of all users who highly rated the game).

    A lift of 3.0 means fans of the liked games are 3x more likely to
    love this game than the average BGG user.
    """
    if not liked_bgg_ids:
        return []

    row = conn.execute(
        "SELECT value FROM metadata WHERE key = 'total_users'"
    ).fetchone()
    if row is None:
        raise RuntimeError("Database has no 'total_users' metadata. Run build_stats first.")
    total_users = int(row[0])
    if total_users == 0:
        return []

    id_ph = ",".join("?" * len(liked_bgg_ids))

    rows = conn.execute(f"""
        WITH
          fan_users AS (
            SELECT DISTINCT user_id
            FROM   ratings
            WHERE  bgg_id IN ({id_ph}) AND rating >= ?
          ),
          n_fans(cnt) AS (SELECT COUNT(*) FROM fan_users),
          fan_high AS (
            SELECT  r.bgg_id,
                    COUNT(*) AS fan_high_count
            FROM    ratings r
            JOIN    fan_users fu ON r.user_id = fu.user_id
            WHERE   r.rating >= ?
              AND   r.bgg_id NOT IN ({id_ph})
            GROUP   BY r.bgg_id
            HAVING  COUNT(*) >= ?
          )
        SELECT
          fh.bgg_id,
          CAST(fh.fan_high_count AS REAL) / nf.cnt                     AS fan_rate,
          CAST(gs.high_rating_count AS REAL) / ?                       AS base_rate,
          (CAST(fh.fan_high_count AS REAL) / nf.cnt) /
          (CAST(gs.high_rating_count AS REAL) / ?)                     AS lift
        FROM  fan_high fh
        JOIN  game_stats gs  ON fh.bgg_id = gs.bgg_id
        CROSS JOIN n_fans nf
        WHERE gs.high_rating_count > 0
        ORDER BY lift DESC
        LIMIT ?
    """, (
        *liked_bgg_ids, min_rating,          # fan_users CTE
        min_rating, *liked_bgg_ids,          # fan_high CTE
        min_fan_count,                       # HAVING
        total_users, total_users,            # base_rate + lift
        top_n,
    )).fetchall()

    return [(row[0], row[3]) for row in rows]
```

**Step 4: Run all tests**

```bash
pytest tests/ -v
```

Expected: all pass.

**Step 5: Commit**

```bash
git add bgg/recommender.py tests/test_recommender.py
git commit -m "feat: add lift-based collaborative filtering recommender"
```

---

### Task 7: One-time import script

**Files:**
- Create: `import_ratings.py`

No tests — this is a thin orchestration script; all its components are tested individually.

**Step 1: Create `import_ratings.py`**

```python
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
```

**Step 2: Verify script help text works**

```bash
python import_ratings.py
```

Expected: prints `Usage: python import_ratings.py <path-to-ratings.csv>` and exits with code 1.

**Step 3: Commit**

```bash
git add import_ratings.py
git commit -m "feat: add one-time Kaggle CSV import script"
```

---

### Task 8: CLI entry point

**Files:**
- Create: `recommend.py`

No automated tests for the CLI — the core logic is tested. Manual smoke test with a real database.

**Step 1: Create `recommend.py`**

```python
"""
Board game recommender CLI.

Usage:
  python recommend.py "Wingspan" "Terraforming Mars" "Agricola"
  python recommend.py "Wingspan" -n 5
"""

import argparse
import sqlite3
import sys
from pathlib import Path

from bgg.api import BGGClient
from bgg.database import ensure_game_cached, open_db
from bgg.recommender import get_recommendations

DB_PATH    = Path("data/bgg.db")
DEFAULT_N  = 10


def resolve_game(
    name:   str,
    client: BGGClient,
    conn:   sqlite3.Connection,
) -> int | None:
    """Search BGG for a game by name. Prompts user to pick if ambiguous."""
    results = client.search(name)
    if not results:
        print(f"  Warning: no BGG results for '{name}', skipping.")
        return None

    # Prefer exact case-insensitive match
    exact = [r for r in results if r.name.lower() == name.lower()]
    if len(exact) == 1:
        return exact[0].bgg_id

    candidates = (exact or results)[:5]
    print(f"\nMultiple results for '{name}':")
    for i, r in enumerate(candidates, 1):
        year = f" ({r.year})" if r.year else ""
        print(f"  {i}. {r.name}{year}  [BGG ID {r.bgg_id}]")
    print("  0. Skip")

    while True:
        try:
            choice = int(input("Enter number: ").strip())
        except (ValueError, EOFError):
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

    recommendations = get_recommendations(liked_ids, conn, top_n=args.top)
    if not recommendations:
        print("No recommendations found. Try adding more liked games.")
        conn.close()
        sys.exit(0)

    print(f"{'#':<4}  {'Game':<45}  {'Lift':>5}  {'Rank':>6}  {'Avg':>5}")
    print("─" * 72)
    for rank, (bgg_id, lift) in enumerate(recommendations, 1):
        ensure_game_cached(bgg_id, client, conn)
        row = conn.execute(
            "SELECT name, bgg_rank, rating_avg FROM games WHERE bgg_id = ?",
            (bgg_id,),
        ).fetchone()
        name     = row[0] if row else f"BGG ID {bgg_id}"
        bgg_rank = f"#{row[1]}" if row and row[1] else "N/A"
        avg      = f"{row[2]:.2f}" if row and row[2] else "N/A"
        print(f"{rank:<4}  {name:<45}  {lift:>5.2f}  {bgg_rank:>6}  {avg:>5}")

    conn.close()


if __name__ == "__main__":
    main()
```

**Step 2: Run all tests to confirm nothing broke**

```bash
pytest tests/ -v
```

Expected: all pass.

**Step 3: Commit**

```bash
git add recommend.py
git commit -m "feat: add CLI entry point"
```

---

### Task 9: Final integration check

**Step 1: Run full test suite**

```bash
pytest tests/ -v
```

Expected: all tests pass.

**Step 2: Check script help**

```bash
python recommend.py --help
python import_ratings.py
```

Expected: both print usage without errors.

**Step 3: Commit (if any cleanup was needed)**

```bash
git add -A
git commit -m "chore: final cleanup"
```

---

## Post-Implementation: Using the App

```bash
# 1. Download the Kaggle dataset to data/bgg-reviews.csv
# 2. Import (takes a few minutes for 13M rows)
python import_ratings.py data/bgg-reviews.csv

# 3. Get recommendations
python recommend.py "Wingspan" "Terraforming Mars" "Agricola"
python recommend.py "Gloomhaven" "Pandemic" -n 5
```
