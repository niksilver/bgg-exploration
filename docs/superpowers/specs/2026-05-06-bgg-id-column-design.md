# Design: `--id` CLI option

## Overview

Add a `--id` boolean flag to `recommend.py` that, when present, inserts a BGG ID column in the output table between the `#` and `Game` columns.

## Changes

All changes are confined to `recommend.py`.

### Argument parsing

Add `--id` as a `store_true` flag:

```python
parser.add_argument(
    "--id", action="store_true",
    help="Include BGG ID in output",
)
```

### `_format_row()` signature

Add two optional parameters:

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
    show_id:    bool = False,
) -> str:
```

When `show_id` is `True`, a right-aligned 6-character ID field is inserted between the rank and the name:

- First line: `f"{i:<4}  {bgg_id:>6}  {lines[0]:<{name_width}}  {stats}"`
- Continuation indent widens from 6 to 14 spaces to maintain name column alignment.

When `show_id` is `False`, behaviour is identical to today.

### Header

When `--id` is set, the header includes an `ID` column in the same position:

```
                                                                               Fan
#     ID      Game                                           Lift    Rank    Avg  avg
───────────────────────────────────────────────────────────────────────────────────────
```

Total line width: 87 characters (up from 79).

### Call site

```python
print(_format_row(i, name, lift, bgg_rank, avg, fan_avg, bgg_id=bgg_id, show_id=args.id))
```

## Testing

Extend `tests/test_recommend.py`:

- `test_format_row_with_id_shows_id_column` — verifies the ID appears between `#` and name on a single-line row.
- `test_format_row_with_id_long_name_wraps` — verifies stats still appear only on the last line and continuation lines use the wider indent.
- `test_format_row_without_id_unchanged` — verifies existing behaviour is unaffected (no regression).
