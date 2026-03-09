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
        raise RuntimeError("Database has no 'total_users' metadata. Run build_stats first.")
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
        LEFT JOIN games g    ON fh.bgg_id = g.bgg_id
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
