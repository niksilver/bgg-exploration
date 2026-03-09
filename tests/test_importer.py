import csv
import re
import pytest
from unittest.mock import patch
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


def test_import_ratings_prints_progress_every_second(tmp_path, capsys):
    csv_path = tmp_path / "ratings.csv"
    _write_csv(csv_path, [
        {"user": "alice", "ID": "1", "name": "Wingspan", "rating": "9"},
        {"user": "bob",   "ID": "1", "name": "Wingspan", "rating": "8"},
        {"user": "carol", "ID": "2", "name": "Agricola", "rating": "7"},
    ])
    conn = open_db(tmp_path / "test.db")

    # Simulate: init=0.0, row1 check=1.5s elapsed (triggers print),
    # row2 check=1.5s (no change, no print), row3 check=1.5s (no print)
    with patch("bgg.importer.time.monotonic", side_effect=[0.0, 1.5, 1.5, 1.5]):
        import_ratings(csv_path, conn)

    lines = [l for l in capsys.readouterr().out.splitlines() if "records" in l]
    assert len(lines) == 1
    assert re.match(r"\[\d{2}:\d{2}:\d{2}\] \d[\d,]* records processed", lines[0])


def test_build_stats_computes_rating_avg(tmp_path):
    csv_path = tmp_path / "ratings.csv"
    _write_csv(csv_path, [
        {"user": "alice", "ID": "1", "name": "Wingspan", "rating": "9"},
        {"user": "bob",   "ID": "1", "name": "Wingspan", "rating": "7"},
        {"user": "carol", "ID": "2", "name": "Agricola", "rating": "8"},
    ])
    conn = open_db(tmp_path / "test.db")
    import_ratings(csv_path, conn)

    build_stats(conn, min_rating=8.0)

    row = conn.execute(
        "SELECT rating_avg FROM game_stats WHERE bgg_id=1"
    ).fetchone()
    assert row[0] == pytest.approx(8.0)  # (9+7)/2 = 8.0


def test_import_ratings_raises_on_missing_columns(tmp_path):
    csv_path = tmp_path / "wrong.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["ID", "Name", "Average"])
        writer.writeheader()
        writer.writerow({"ID": "30549", "Name": "Pandemic", "Average": "7.59"})
    conn = open_db(tmp_path / "test.db")

    with pytest.raises(ValueError, match="user.*rating"):
        import_ratings(csv_path, conn)
