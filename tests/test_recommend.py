import pytest

from bgg.database import open_db
from recommend import _format_row, _parse_game_input, resolve_game, GameSearchResult


def test_format_row_short_name_single_line():
    """A name that fits within name_width produces a single line with stats at the end."""
    row = _format_row(1, "Wingspan", 3.45, "#21", "8.07", name_width=10)
    assert "\n" not in row
    assert "Wingspan" in row
    assert "3.45" in row


def test_format_row_long_name_wraps():
    """A name longer than name_width wraps; stats appear only on the last line."""
    row = _format_row(3, "A Very Long Game Name", 1.50, "N/A", "7.50", name_width=10)
    lines = row.split("\n")
    assert len(lines) > 1
    assert "1.50" in lines[-1]
    assert "1.50" not in lines[0]


def test_format_row_continuation_lines_indented():
    """Continuation lines of a wrapped name are indented to align with the name column."""
    row = _format_row(1, "A Very Long Game Name", 1.50, "N/A", "7.50", name_width=10)
    lines = row.split("\n")
    for line in lines[1:]:
        assert line.startswith("      ")


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
