# BGG ID Column Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `--id` boolean flag to `recommend.py` that inserts a BGG ID column between `#` and `Game` in the output table.

**Architecture:** All changes are confined to `recommend.py`. `_format_row()` gains two optional parameters (`bgg_id`, `show_id`) to handle ID rendering and the wider continuation-line indent. `main()` adds the argparse flag, a conditional header branch, and passes the new params to `_format_row()`.

**Tech Stack:** Python 3.11+, argparse, textwrap (already in use)

**Status:** Not started

---

## Files

- Modify: `recommend.py` — `_format_row()` signature/body, argparse, header, call site
- Test: `tests/test_recommend.py` — three new tests for `_format_row()` with ID

---

### Task 1: Extend `_format_row()` to support the ID column (TDD)

**Files:**
- Modify: `recommend.py` — `_format_row()` only
- Test: `tests/test_recommend.py`

**Status:** Not started

- [ ] **Step 1: Write three failing tests**

  Add to `tests/test_recommend.py`:

  ```python
  def test_format_row_with_id_shows_id_between_rank_and_name():
      row = _format_row(1, "Wingspan", 3.45, "#21", "8.07", "8.50",
                        name_width=10, bgg_id=266192, show_id=True)
      assert "266192" in row
      assert row.index("266192") < row.index("Wingspan")

  def test_format_row_with_id_long_name_continuation_uses_wider_indent():
      row = _format_row(3, "A Very Long Game Name", 1.50, "N/A", "7.50", "8.20",
                        name_width=10, bgg_id=12345, show_id=True)
      lines = row.split("\n")
      assert len(lines) > 1
      for line in lines[1:]:
          assert line.startswith("              ")  # 14 spaces

  def test_format_row_show_id_false_is_identical_to_default():
      row_default = _format_row(1, "Wingspan", 3.45, "#21", "8.07", "8.50", name_width=10)
      row_off     = _format_row(1, "Wingspan", 3.45, "#21", "8.07", "8.50",
                                name_width=10, bgg_id=266192, show_id=False)
      assert row_default == row_off
  ```

- [ ] **Step 2: Run the tests to confirm they fail**

  ```bash
  pytest tests/test_recommend.py::test_format_row_with_id_shows_id_between_rank_and_name \
         tests/test_recommend.py::test_format_row_with_id_long_name_continuation_uses_wider_indent \
         tests/test_recommend.py::test_format_row_show_id_false_is_identical_to_default -v
  ```

  Expected: all three FAIL (TypeError — unexpected keyword arguments).

- [ ] **Step 3: Extend `_format_row()` in `recommend.py`**

  Add `bgg_id: int | None = None` and `show_id: bool = False` to the signature (after `name_width`).

  In the body, branch on `show_id`:

  - When `show_id` is `True`: format `bgg_id` as `f"{bgg_id:>6}"`, use `"              "` (14 spaces) for continuation indent, and insert the ID field between the rank and name on the first/last line.
    - 14 spaces = 4 (`i:<4`) + 2 (sep) + 6 (id) + 2 (sep)
    - Single-line: `f"{i:<4}  {bgg_id:>6}  {lines[0]:<{name_width}}  {stats}"`
    - First line of multi: `f"{i:<4}  {bgg_id:>6}  {lines[0]}"`
    - Middle lines: `f"              {line}"`
    - Last line: `f"              {lines[-1]:<{name_width}}  {stats}"`
  - When `show_id` is `False`: leave the existing code unchanged.

- [ ] **Step 4: Run the tests to confirm they all pass**

  ```bash
  pytest tests/test_recommend.py -v
  ```

  Expected: all existing tests plus the three new ones PASS.

- [ ] **Step 5: Commit**

  ```bash
  git add recommend.py tests/test_recommend.py
  git commit -m "feat: extend _format_row to support optional BGG ID column"
  ```

---

### Task 2: Wire `--id` into `main()`

**Files:**
- Modify: `recommend.py` — `main()` only (argparse, header, call site)

**Status:** Not started

- [ ] **Step 1: Add the `--id` argparse flag**

  In `main()`, after the existing `--not` argument, add:

  ```python
  parser.add_argument(
      "--id", action="store_true",
      help="Include BGG ID in output",
  )
  ```

- [ ] **Step 2: Update the header to branch on `args.id`**

  The current header block (lines ~179–181) prints three lines unconditionally. Replace it with a branch:

  - When `args.id` is `False` (unchanged):
    ```
    f"{'':75}{'Fan':>4}"
    f"{'#':<4}  {'Game':<{NAME_W}}  {'Lift':>5}  {'Rank':>6}  {'Avg':>5}  {'avg':>4}"
    "─" * 79
    ```
  - When `args.id` is `True` (extra ID column, everything shifts right 8 chars):
    ```
    f"{'':83}{'Fan':>4}"
    f"{'#':<4}  {'ID':>6}  {'Game':<{NAME_W}}  {'Lift':>5}  {'Rank':>6}  {'Avg':>5}  {'avg':>4}"
    "─" * 87
    ```

- [ ] **Step 3: Update the `_format_row()` call site**

  The call at the bottom of the `for` loop currently is:

  ```python
  print(_format_row(i, name, lift, bgg_rank, avg, fan_avg))
  ```

  Change it to:

  ```python
  print(_format_row(i, name, lift, bgg_rank, avg, fan_avg, bgg_id=bgg_id, show_id=args.id))
  ```

  `bgg_id` is already available as the first element of each `recommendations` tuple (the loop is `for i, (bgg_id, lift, fan_avg_val) in enumerate(recommendations, 1):`).

- [ ] **Step 4: Run the full test suite**

  ```bash
  pytest tests/ -v
  ```

  Expected: all tests PASS.

- [ ] **Step 5: Commit**

  ```bash
  git add recommend.py
  git commit -m "feat: add --id flag to include BGG ID column in output"
  ```
