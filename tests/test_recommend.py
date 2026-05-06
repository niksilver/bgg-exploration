import argparse
import pytest

from bgg.database import open_db
from recommend import (
    _format_row, _parse_game_input, _parse_show,
    resolve_game, GameSearchResult, DEFAULT_COLUMNS,
)


def test_format_row_short_name_single_line():
    row = _format_row(1, "Wingspan", 3.45, "#21", "8.07", "8.50",
                      name_width=10,
                      shown=frozenset({"order", "name", "lift", "rank", "avg", "fanavg"}))
    assert "\n" not in row
    assert "Wingspan" in row
    assert "3.45" in row
    assert "8.50" in row


def test_format_row_long_name_wraps():
    row = _format_row(3, "A Very Long Game Name", 1.50, "N/A", "7.50", "8.20",
                      name_width=10,
                      shown=frozenset({"order", "name", "lift", "rank", "avg", "fanavg"}))
    lines = row.split("\n")
    assert len(lines) > 1
    assert "1.50" in lines[-1]
    assert "1.50" not in lines[0]


def test_format_row_continuation_lines_indented():
    row = _format_row(1, "A Very Long Game Name", 1.50, "N/A", "7.50", "8.20",
                      name_width=10)
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


def test_format_row_with_id_shows_id_between_rank_and_name():
    row = _format_row(1, "Wingspan", 3.45, "#21", "8.07", "8.50",
                      name_width=10, bgg_id=266192,
                      shown=frozenset({"order", "id", "name", "rank", "avg", "fanavg"}))
    assert "266192" in row
    assert row.index("266192") < row.index("Wingspan")


def test_format_row_with_id_long_name_continuation_uses_wider_indent():
    row = _format_row(3, "A Very Long Game Name", 1.50, "N/A", "7.50", "8.20",
                      name_width=10, bgg_id=12345,
                      shown=frozenset({"order", "id", "name", "rank", "avg", "fanavg"}))
    lines = row.split("\n")
    assert len(lines) > 1
    for line in lines[1:]:
        assert line.startswith("              ")  # 14 spaces


def test_format_row_default_shown_excludes_id():
    row = _format_row(1, "Wingspan", 3.45, "#21", "8.07", "8.50",
                      name_width=10, bgg_id=266192)
    assert "266192" not in row


def test_format_row_with_lift_shows_lift_value():
    row = _format_row(1, "Wingspan", 3.45, "#21", "8.07", "8.50",
                      name_width=10,
                      shown=frozenset({"order", "name", "lift", "rank", "avg", "fanavg"}))
    assert "3.45" in row


def test_format_row_without_lift_omits_lift_value():
    row = _format_row(1, "Wingspan", 3.45, "#21", "8.07", "8.50",
                      name_width=10, shown=DEFAULT_COLUMNS)
    assert "3.45" not in row


def test_format_row_without_lift_still_shows_rank_avg_fan_avg():
    row = _format_row(1, "Wingspan", 3.45, "#21", "8.07", "8.50",
                      name_width=10, shown=DEFAULT_COLUMNS)
    assert "#21" in row
    assert "8.07" in row
    assert "8.50" in row


def test_format_row_without_lift_long_name_wraps_with_stats_on_last_line():
    row = _format_row(3, "A Very Long Game Name", 1.50, "N/A", "7.50", "8.20",
                      name_width=10, shown=DEFAULT_COLUMNS)
    lines = row.split("\n")
    assert len(lines) > 1
    assert "1.50" not in lines[-1]
    assert "N/A" in lines[-1]


def test_parse_show_adds_column_not_in_default():
    result = _parse_show("id", DEFAULT_COLUMNS)
    assert "id" in result
    assert "name" in result          # default column still present


def test_parse_show_removes_column_from_default():
    result = _parse_show("-rank", DEFAULT_COLUMNS)
    assert "rank" not in result
    assert "name" in result          # other default columns untouched


def test_parse_show_mixed_add_and_remove():
    result = _parse_show("id,-rank", DEFAULT_COLUMNS)
    assert "id" in result
    assert "rank" not in result
    assert "name" in result


def test_parse_show_unknown_column_raises_error():
    with pytest.raises(argparse.ArgumentTypeError):
        _parse_show("bogus", DEFAULT_COLUMNS)


def test_parse_show_reinforcing_present_column_is_noop():
    result = _parse_show("name", DEFAULT_COLUMNS)
    assert result == DEFAULT_COLUMNS


def test_parse_show_removing_absent_column_is_noop():
    result = _parse_show("-lift", DEFAULT_COLUMNS)
    assert result == DEFAULT_COLUMNS
