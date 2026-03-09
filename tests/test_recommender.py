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
