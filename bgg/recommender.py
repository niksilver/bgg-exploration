import sqlite3


def get_recommendations(
    liked_bgg_ids: list[int],
    conn:          sqlite3.Connection,
    min_rating:    float     = 8.0,
    min_fan_count: int       = 100,
    top_n:         int       = 10,
    min_avg:       float     = 0.0,
    exclusions:    list[str] = [],
) -> list[tuple[int, float]]:
    """
    Return (bgg_id, lift) pairs sorted by lift descending.

    Lift = (fraction of fans who highly rated the game) /
           (fraction of all users who highly rated the game).

    A lift of 3.0 means fans of the liked games are 3x more likely to
    love this game than the average BGG user.

    min_fan_count: minimum number of fans (users who liked the input games)
                   who also highly rated the candidate game. Filters out games
                   with very few co-occurrence signals.
    """
    if not liked_bgg_ids:
        return []

    row = conn.execute(
        "SELECT value FROM metadata WHERE key = 'total_users'"
    ).fetchone()
    if row is None:
        raise RuntimeError(
            "Database has no 'total_users' metadata. "
            "Run: python import_ratings.py <path-to-csv>"
        )
    total_users = int(row[0])
    if total_users == 0:
        return []

    id_ph      = ",".join("?" * len(liked_bgg_ids))
    excl_sql   = "".join(
        "  AND (g.name IS NULL OR LOWER(g.name) NOT LIKE ?)\n"
        for _ in exclusions
    )
    excl_params = [f"%{e.lower()}%" for e in exclusions]

    rows = conn.execute(f"""
        WITH
          -- Step 1: Identify the "fans" — users who gave at least one of the
          -- input games a high rating. These are the people whose tastes we are
          -- trying to match. Every subsequent calculation is scoped to this group.
          fan_users AS (
            SELECT DISTINCT user_id
            FROM   ratings
            WHERE  bgg_id IN ({id_ph}) AND rating >= ?
          ),

          -- Step 2: Count the fans. Stored as a single-row CTE so we can
          -- reference it as a scalar value in the final SELECT without a
          -- correlated subquery.
          n_fans(cnt) AS (SELECT COUNT(*) FROM fan_users),

          -- Step 3: For each candidate game, count how many fans gave it a
          -- high rating. We exclude the input games themselves (they must not
          -- appear in the recommendations), and we require a minimum number of
          -- fan votes (min_fan_count) to filter out games with too little
          -- co-occurrence signal.
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

        -- Step 4: Compute lift for every candidate game that survived the
        -- fan_high filter.
        --
        -- fan_rate  = fan_high_count / n_fans
        --           = the fraction of fans who gave this game a high rating.
        --
        -- base_rate = gs.high_rating_count / total_users
        --           = the fraction of ALL users in the dataset who gave this
        --             game a high rating. Pre-computed in game_stats so we
        --             don't have to scan the full ratings table here.
        --
        -- lift      = fan_rate / base_rate
        --           = how much more likely fans of the input games are to love
        --             this game compared with a randomly chosen user. A lift of
        --             3.0 means fans are three times as likely to rate it highly.
        --
        -- We exclude games where high_rating_count is zero to avoid division
        -- by zero in the base_rate calculation.
        --
        -- Optional filters:
        --   min_avg   — skip games whose average Kaggle rating falls below the
        --               threshold. The (? = 0.0 OR ...) pattern means a value
        --               of 0.0 disables the filter entirely.
        --   exclusions — one NOT LIKE clause per --not argument, injected as
        --               {excl_sql.strip() or '(none)'}.
        SELECT
          fh.bgg_id,
          CAST(fh.fan_high_count AS REAL) / nf.cnt                     AS fan_rate,
          CAST(gs.high_rating_count AS REAL) / ?                       AS base_rate,
          (CAST(fh.fan_high_count AS REAL) / nf.cnt) /
          (CAST(gs.high_rating_count AS REAL) / ?)                     AS lift
        FROM  fan_high fh
        JOIN  game_stats gs  ON fh.bgg_id = gs.bgg_id
        INNER JOIN games g   ON fh.bgg_id = g.bgg_id
        CROSS JOIN n_fans nf
        WHERE gs.high_rating_count > 0
          AND (? = 0.0 OR gs.rating_avg >= ?)
{excl_sql}        ORDER BY lift DESC
        LIMIT ?
    """, (
        *liked_bgg_ids, min_rating,          # fan_users CTE
        min_rating, *liked_bgg_ids,          # fan_high CTE
        min_fan_count,                       # HAVING
        total_users, total_users,            # base_rate + lift
        min_avg, min_avg,                    # min_avg filter
        *excl_params,                        # exclusions
        top_n,
    )).fetchall()

    return [(row[0], row[3]) for row in rows]
