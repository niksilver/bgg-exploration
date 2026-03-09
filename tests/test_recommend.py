from unittest.mock import MagicMock

import pytest

from bgg.api import GameSearchResult
from bgg.database import open_db
from recommend import _parse_game_input, resolve_game


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
    client = MagicMock()
    client.search.return_value = [
        GameSearchResult(bgg_id=1, name="Catan", year=1995),
        GameSearchResult(bgg_id=2, name="Catan", year=2015),
    ]

    result = resolve_game("Catan (1995)", client, conn)

    assert result == 1
    client.search.assert_called_once_with("Catan")


def test_resolve_game_shows_menu_when_year_still_ambiguous(tmp_path, monkeypatch):
    conn = open_db(tmp_path / "test.db")
    client = MagicMock()
    client.search.return_value = [
        GameSearchResult(bgg_id=1, name="Catan", year=1995),
        GameSearchResult(bgg_id=2, name="Catan", year=1995),
    ]
    monkeypatch.setattr("builtins.input", lambda _: "2")

    result = resolve_game("Catan (1995)", client, conn)

    assert result == 2


def test_resolve_game_shows_full_menu_when_year_has_no_matches(tmp_path, monkeypatch):
    conn = open_db(tmp_path / "test.db")
    client = MagicMock()
    client.search.return_value = [
        GameSearchResult(bgg_id=1, name="Catan", year=1995),
        GameSearchResult(bgg_id=2, name="Catan", year=2015),
    ]
    monkeypatch.setattr("builtins.input", lambda _: "1")

    result = resolve_game("Catan (2000)", client, conn)  # no match for 2000

    assert result == 1  # falls back to full candidate list
