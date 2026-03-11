import pytest

from bgg.database import open_db
from recommend import _parse_game_input, resolve_game, GameSearchResult


def test_parse_extracts_year():
    assert _parse_game_input("Catan (1995)") == ("Catan", 1995)


def test_parse_no_year():
    assert _parse_game_input("Wingspan") == ("Wingspan", None)


def test_parse_non_year_parens_not_treated_as_year():
    assert _parse_game_input("Catan (Board Game)") == ("Catan (Board Game)", None)


def test_parse_year_after_subtitle():
    assert _parse_game_input("Wingspan (Second Edition) (2019)") == (
        "Wingspan (Second Edition)", 2019
    )


def test_resolve_game_uses_year_to_disambiguate(tmp_path):
    conn = open_db(tmp_path / "test.db")
    conn.executemany(
        "INSERT INTO games(bgg_id, name, year_published) VALUES (?, ?, ?)",
        [(1, "Catan", 1995), (2, "Catan", 2015)],
    )
    conn.commit()

    result = resolve_game("Catan (1995)", conn)

    assert result == 1


def test_resolve_game_shows_menu_when_year_still_ambiguous(tmp_path, monkeypatch):
    conn = open_db(tmp_path / "test.db")
    conn.executemany(
        "INSERT INTO games(bgg_id, name, year_published) VALUES (?, ?, ?)",
        [(1, "Catan", 1995), (2, "Catan", 1995)],
    )
    conn.commit()
    monkeypatch.setattr("builtins.input", lambda _: "2")

    result = resolve_game("Catan (1995)", conn)

    assert result == 2


def test_resolve_game_searches_local_db(tmp_path):
    conn = open_db(tmp_path / "test.db")
    conn.execute("INSERT INTO games(bgg_id, name) VALUES (?, ?)", (266192, "Wingspan"))
    conn.commit()

    result = resolve_game("Wingspan", conn)

    assert result == 266192


def test_resolve_game_returns_none_when_not_in_db(tmp_path, capsys):
    conn = open_db(tmp_path / "test.db")

    result = resolve_game("Obscure Game", conn)

    assert result is None
    assert "no results" in capsys.readouterr().out


def test_resolve_game_shows_full_menu_when_year_has_no_matches(tmp_path, monkeypatch):
    conn = open_db(tmp_path / "test.db")
    conn.executemany(
        "INSERT INTO games(bgg_id, name, year_published) VALUES (?, ?, ?)",
        [(1, "Catan", 1995), (2, "Catan", 2015)],
    )
    conn.commit()
    monkeypatch.setattr("builtins.input", lambda _: "1")

    result = resolve_game("Catan (2000)", conn)  # no match for 2000

    assert result == 1  # falls back to full candidate list
