# `--show` Column Selector Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the `--id` and `--lift` boolean flags with a single `--show` flag that adds/removes columns from a default set.

**Architecture:** A standalone `_parse_show` function converts the `--show` string into a `frozenset[str]` of visible column names. `_format_row` and the header-printing code in `main()` are driven by this set. Column display order is always fixed; the set only controls visibility.

**Tech Stack:** Python stdlib only — `argparse`, `textwrap`, `frozenset`.

**Status:** Not started

---

## Files

- Modify: `recommend.py` — add constants, `_parse_show`, refactor `_format_row`, update `main()`
- Modify: `tests/test_recommend.py` — add `_parse_show` tests, update `_format_row` tests
- Modify: `README.md` — update CLI options table

---

## Task 1: Add column constants and `_parse_show`

**Files:**
- Modify: `recommend.py` (after the existing `NAME_W` constant)
- Modify: `tests/test_recommend.py`

**Status:** Not started

- [ ] **Step 1: Add failing tests for `_parse_show`**

  In `tests/test_recommend.py`, update the import line to also import `_parse_show` and `DEFAULT_COLUMNS`:

  ```python
  from recommend import (
      _format_row, _parse_game_input, _parse_show,
      resolve_game, GameSearchResult, DEFAULT_COLUMNS,
  )
  ```

  Then add these six tests at the bottom of the file:

  ```python
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
  ```

  Also add `import argparse` to the test file imports (needed for `argparse.ArgumentTypeError`).

- [ ] **Step 2: Run the new tests and confirm they fail**

  ```bash
  python -m pytest tests/test_recommend.py -k "parse_show" -v
  ```

  Expected: all six `test_parse_show_*` tests fail with `ImportError` (names not yet defined).

- [ ] **Step 3: Add column constants to `recommend.py`**

  After the existing constants (`DB_PATH`, `DEFAULT_N`, `NAME_W`), add:

  ```python
  COL_ORDER       = ("order", "id", "name", "lift", "rank", "avg", "fanavg")
  ALL_COLUMNS     = frozenset(COL_ORDER)
  DEFAULT_COLUMNS = frozenset({"order", "name", "rank", "avg", "fanavg"})
  COL_WIDTHS      = {"order": 4, "id": 6, "name": NAME_W, "lift": 5,
                     "rank": 6, "avg": 5, "fanavg": 4}
  COL_HDRS        = {"order": "#",    "id": "ID",   "name": "Game", "lift": "Lift",
                     "rank": "Rank", "avg": "Avg", "fanavg": "avg"}
  COL_ALIGN       = {"order": "<", "id": ">", "name": "<", "lift": ">",
                     "rank": ">", "avg": ">", "fanavg": ">"}
  ```

- [ ] **Step 4: Add `_parse_show` to `recommend.py`**

  Place it just before `_format_row`. Its signature and logic:

  ```python
  def _parse_show(value: str, default: frozenset[str]) -> frozenset[str]:
      shown = set(default)
      for token in value.split(","):
          token = token.strip()
          col   = token[1:] if token.startswith("-") else token
          if col not in ALL_COLUMNS:
              raise argparse.ArgumentTypeError(
                  f"unknown column '{col}' (valid: {', '.join(COL_ORDER)})"
              )
          if token.startswith("-"):
              shown.discard(col)
          else:
              shown.add(col)
      return frozenset(shown)
  ```

- [ ] **Step 5: Run the new tests and confirm they pass**

  ```bash
  python -m pytest tests/test_recommend.py -k "parse_show" -v
  ```

  Expected: all six tests pass.

- [ ] **Step 6: Run the full suite and confirm nothing else broke**

  ```bash
  python -m pytest -q
  ```

  Expected: all tests pass.

- [ ] **Step 7: Commit**

  ```bash
  git add recommend.py tests/test_recommend.py
  git commit -m "feat: add _parse_show and column constants"
  ```

---

## Task 2: Refactor `_format_row` to use `shown`

**Files:**
- Modify: `recommend.py` (`_format_row` function, lines ~32–70)
- Modify: `tests/test_recommend.py` (all `_format_row` tests)

**Status:** Not started

- [ ] **Step 1: Update existing `_format_row` tests**

  Replace the existing `_format_row` tests in `tests/test_recommend.py` with the versions below. The only changes are: `show_id=True/False` and `show_lift=True/False` become `shown=frozenset({...})`.

  ```python
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
  ```

  Note: `test_format_row_show_id_false_is_identical_to_default` is replaced by `test_format_row_default_shown_excludes_id`.

- [ ] **Step 2: Run the updated tests and confirm they fail**

  ```bash
  python -m pytest tests/test_recommend.py -k "format_row" -v
  ```

  Expected: most `test_format_row_*` tests fail with `TypeError: unexpected keyword argument 'shown'`.

- [ ] **Step 3: Replace `_format_row` in `recommend.py`**

  Replace the entire `_format_row` function (currently lines ~32–70) with:

  ```python
  def _format_row(
      i:          int,
      name:       str,
      lift:       float,
      bgg_rank:   str,
      avg:        str,
      fan_avg:    str,
      name_width: int = NAME_W,
      bgg_id:     int | None = None,
      shown:      frozenset[str] = DEFAULT_COLUMNS,
  ) -> str:
      """Format one recommendation row, wrapping long names across multiple lines."""
      pre_parts = []
      if "order" in shown:
          pre_parts.append(f"{i:<4}")
      if "id" in shown:
          assert bgg_id is not None, "bgg_id must be provided when 'id' in shown"
          pre_parts.append(f"{bgg_id:>6}")
      prefix = ("  ".join(pre_parts) + "  ") if pre_parts else ""
      indent = " " * len(prefix)

      stat_parts = []
      if "lift" in shown:
          stat_parts.append(f"{lift:>5.2f}")
      if "rank" in shown:
          stat_parts.append(f"{bgg_rank:>6}")
      if "avg" in shown:
          stat_parts.append(f"{avg:>5}")
      if "fanavg" in shown:
          stat_parts.append(f"{fan_avg:>4}")
      stats = "  ".join(stat_parts)

      if "name" not in shown:
          return (prefix + stats).rstrip()

      lines = textwrap.wrap(name, name_width) or [""]
      if len(lines) == 1:
          return prefix + f"{lines[0]:<{name_width}}  {stats}"
      parts = [prefix + lines[0]]
      for line in lines[1:-1]:
          parts.append(indent + line)
      parts.append(indent + f"{lines[-1]:<{name_width}}  {stats}")
      return "\n".join(parts)
  ```

- [ ] **Step 4: Run the updated tests and confirm they pass**

  ```bash
  python -m pytest tests/test_recommend.py -k "format_row" -v
  ```

  Expected: all `test_format_row_*` tests pass.

- [ ] **Step 5: Run the full suite**

  ```bash
  python -m pytest -q
  ```

  Expected: all tests pass.

- [ ] **Step 6: Commit**

  ```bash
  git add recommend.py tests/test_recommend.py
  git commit -m "refactor: replace show_id/show_lift with shown frozenset in _format_row"
  ```

---

## Task 3: Update `main()` — replace `--id`/`--lift` with `--show`

**Files:**
- Modify: `recommend.py` (`main()` function)

**Status:** Not started

- [ ] **Step 1: Replace the `--id` and `--lift` argument definitions**

  In `main()`, remove:
  ```python
  parser.add_argument(
      "--id", action="store_true",
      help="Include BGG ID in output",
  )
  parser.add_argument(
      "--lift", action="store_true",
      help="Include Lift column in output",
  )
  ```

  Replace with:
  ```python
  parser.add_argument(
      "--show",
      type=lambda s: _parse_show(s, DEFAULT_COLUMNS),
      default=DEFAULT_COLUMNS,
      metavar="COLUMNS",
      help=(
          "Comma-separated columns to add (+) or remove (-) from the default set. "
          "E.g. --show=id,lift  --show=-rank  --show=id,-fanavg. "
          "All columns: order, id, name, lift, rank, avg, fanavg. "
          "Default shows: order, name, rank, avg, fanavg."
      ),
  )
  ```

  After this change `args.show` is always a `frozenset[str]`.

- [ ] **Step 2: Replace header/separator/row-loop code in `main()`**

  Remove the existing block from `stats_w = ...` through the closing `print(_format_row(...))` line inside the `for` loop (lines 207–226 in the current file). That is everything from the width calculations down to and including the `for i, (bgg_id, lift, fan_avg_val)` loop body.

  Replace with:

  ```python
  visible   = [c for c in COL_ORDER if c in args.show]
  hdr_parts = [f"{COL_HDRS[c]:{COL_ALIGN[c]}{COL_WIDTHS[c]}}" for c in visible]
  header    = "  ".join(hdr_parts)
  total_w   = len(header)
  if "fanavg" in args.show:
      print(f"{'':>{total_w - 4}}{'Fan':>4}")
  print(header)
  print("─" * total_w)
  for i, (bgg_id, lift, fan_avg_val) in enumerate(recommendations, 1):
      row = conn.execute(
          "SELECT name, bgg_rank, rating_avg FROM games WHERE bgg_id = ?",
          (bgg_id,),
      ).fetchone()
      name     = row[0] if row else f"BGG ID {bgg_id}"
      bgg_rank = f"#{row[1]}" if row and row[1] else "N/A"
      avg      = f"{row[2]:.2f}" if row and row[2] else "N/A"
      fan_avg  = f"{fan_avg_val:.2f}" if fan_avg_val is not None else "N/A"
      print(_format_row(i, name, lift, bgg_rank, avg, fan_avg,
                        bgg_id=bgg_id, shown=args.show))
  ```

- [ ] **Step 3: Run the full suite**

  ```bash
  python -m pytest -q
  ```

  Expected: all tests pass.

- [ ] **Step 4: Smoke-test the CLI manually**

  You need a populated `data/bgg.db` for these. If one isn't available, skip to step 5.

  ```bash
  python recommend.py "Wingspan" -n 3
  python recommend.py "Wingspan" -n 3 --show=lift
  python recommend.py "Wingspan" -n 3 --show=id,lift
  python recommend.py "Wingspan" -n 3 --show=-rank
  python recommend.py "Wingspan" -n 3 --show=bogus   # should error
  ```

  Check: default output matches the old default (no id, no lift). `--show=id` matches old `--id`. `--show=lift` matches old `--lift`. `--show=bogus` prints an argparse error.

- [ ] **Step 5: Commit**

  ```bash
  git add recommend.py
  git commit -m "feat: replace --id/--lift with --show column selector"
  ```

---

## Task 4: Update README

**Files:**
- Modify: `README.md`

**Status:** Not started

- [ ] **Step 1: Replace the `--id` and `--lift` rows in the CLI options table**

  Current table rows:
  ```
  | `--id` | off | Include BGG ID column in output (between `#` and game name) |
  | `--lift` | off | Include Lift column in output |
  ```

  Replace with a single row:
  ```
  | `--show COLUMNS` | — | Add or remove optional columns. Bare name adds, `-name` removes from the default set (`order, name, rank, avg, fanavg`). Optional columns: `id`, `lift`. Example: `--show=id,lift` |
  ```

- [ ] **Step 2: Run the full suite one last time**

  ```bash
  python -m pytest -q
  ```

  Expected: all tests pass.

- [ ] **Step 3: Commit**

  ```bash
  git add README.md
  git commit -m "docs: update README for --show flag"
  ```
