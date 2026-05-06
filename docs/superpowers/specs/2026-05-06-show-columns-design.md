# Design: `--show` column selector

## Summary

Replace `--id` and `--lift` boolean flags with a single `--show` option that adds or
removes columns from a default set.

## Column model

Seven named columns in fixed display order:

| Name     | Default | Description              |
|----------|---------|--------------------------|
| `order`  | yes     | Row number (`#`)         |
| `id`     | no      | BGG ID                   |
| `name`   | yes     | Game name                |
| `lift`   | no      | Lift score               |
| `rank`   | yes     | BGG rank                 |
| `avg`    | yes     | BGG average rating       |
| `fanavg` | yes     | Fan average rating       |

Default set: `{order, name, rank, avg, fanavg}`.

## `--show` syntax

Comma-separated tokens. Each token either adds or removes a column from the default set:

- Bare token (`id`, `lift`) — add to shown set
- `-`-prefixed token (`-rank`, `-fanavg`) — remove from shown set

Examples:

```
--show=id,lift        → default + id + lift
--show=-rank          → default − rank
--show=id,-fanavg     → default + id − fanavg
--show=lift           → default + lift
```

Tokens that reinforce the default (e.g. `name` when `name` is already shown, or `-lift`
when `lift` is already absent) are silently accepted.

Unknown column names produce an argparse error:
`error: --show: unknown column 'bogus' (valid: order, id, name, lift, rank, avg, fanavg)`

## Parsing

A standalone function `_parse_show(value, default) -> frozenset[str]` handles the logic:

```python
def _parse_show(value: str, default: frozenset[str]) -> frozenset[str]:
    shown = set(default)
    for token in value.split(","):
        token = token.strip()
        if token.startswith("-"):
            shown.discard(token[1:])
        else:
            shown.add(token)
    return frozenset(shown)
```

Validation (unknown column names) is done before or inside this function and raises
`argparse.ArgumentTypeError`.

## `_format_row` signature

Replace `show_id: bool` and `show_lift: bool` with `shown: frozenset[str]`.
Visibility checks become `"id" in shown` and `"lift" in shown`.
The `bgg_id` parameter is retained (needed when `"id" in shown`).

## Header and separator

The header line and separator width in `main()` are also driven by `shown`, replacing
the current `if not args.id / else` branching with a single code path.

## Testing approach

Tests are written before implementation (TDD).

### `_parse_show` tests
- Bare token adds a column not in the default set
- `-`-prefixed token removes a column from the default set
- Multiple tokens in one call (mix of add and remove)
- Unknown column name raises an error
- Reinforcing an already-present column is a no-op
- Removing an already-absent column is a no-op

### `_format_row` tests
Existing tests updated to use `shown=frozenset({...})` in place of `show_id=` / `show_lift=`.
No new `_format_row` tests needed.

## Migration

`--id` and `--lift` are removed. Equivalent invocations:

| Old                    | New                      |
|------------------------|--------------------------|
| `recommend.py …`       | `recommend.py …`         |
| `recommend.py … --id`  | `recommend.py … --show=id` |
| `recommend.py … --lift`| `recommend.py … --show=lift` |
| `recommend.py … --id --lift` | `recommend.py … --show=id,lift` |
