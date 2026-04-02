# Signal Forge Standards

## Source of Truth

This file is the source of truth for future signal naming, structured signal output,
console formatting, and reporting conventions in Signal Forge.

## Signal Naming

Standard dislocation signal names:

- `CLEAN`
- `MIXED`
- `DISLOCATION`

These values must remain uppercase in structured output, console output, and future
reporting layers unless this document is explicitly revised.

## Dislocation Output Schema

Standard structured fields for dislocation output:

- `signal`
- `pair`
- `futures_symbol`
- `etf_symbol`
- `direction_relation`
- `leader`
- `divergence`
- `divergence_band`
- `explanation`

Field expectations:

- `signal`: one of `CLEAN`, `MIXED`, `DISLOCATION`
- `pair`: display pair identifier such as `CL/XLE`
- `futures_symbol`: futures contract symbol
- `etf_symbol`: ETF symbol
- `direction_relation`: standardized directional relationship value
- `leader`: standardized lead/lag label
- `divergence`: numeric percent divergence between futures and ETF
- `divergence_band`: normalized divergence bucket
- `explanation`: human-readable sentence-case explanation

## Enumerated Values

`direction_relation` values:

- `same_direction`
- `opposite_direction`

`leader` values:

- `futures`
- `etf`
- `none`

`none` is reserved for future near-equal cases where neither side is treated as the
clear leader.

`divergence_band` values:

- `low`
- `moderate`
- `high`

## Formatting Rules

- Structured field names use `snake_case`.
- Divergence is displayed to 2 decimal places.
- Explanation text uses sentence case.
- Console output uses a fixed format.

## Console Template

Standard console template:

```text
[SIGNAL] PAIR | divergence: X.XX% | relation: ... | leader: ...
Explanation: ...
```

Example:

```text
[DISLOCATION] CL/XLE | divergence: 4.10% | relation: same_direction | leader: futures
Explanation: Futures and ETF are moving in the same direction, futures leading while divergence remains high.
```
