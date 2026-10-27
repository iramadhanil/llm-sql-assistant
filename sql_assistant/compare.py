"""How a predicted result is matched against the gold result.

A prediction is correct when it returns the same rows as the gold query:
- row order does not matter;
- extra columns are allowed (a label or a count next to the answer is fine),
  as long as every gold column is found in the prediction;
- whole numbers must match exactly; other numbers may differ by 0.5% or 0.01,
  so rounding to two decimals does not count as a mistake;
- '2017' and 2017 are treated as the same value;
- a one-row answer may hold the values of a one-column reference side by side
  (for example "late vs on time" as two columns instead of two rows).
"""

import math
from itertools import permutations

REL_TOL = 5e-3
ABS_TOL = 1e-2


def _as_number(value):
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip())
        except ValueError:
            return None
    return None


def values_match(a, b) -> bool:
    if a is None or b is None:
        return a is None and b is None
    x, y = _as_number(a), _as_number(b)
    if x is not None and y is not None:
        if math.isnan(x) or math.isnan(y):
            return False
        if x.is_integer() and y.is_integer():
            return x == y
        return math.isclose(x, y, rel_tol=REL_TOL, abs_tol=ABS_TOL)
    return str(a).strip() == str(b).strip()


def _rows_match(a: tuple, b: tuple) -> bool:
    return all(values_match(x, y) for x, y in zip(a, b))


def _same_rows(gold: list, pred: list) -> bool:
    """Multiset comparison: each gold row must pair with a different predicted row."""
    unmatched = list(pred)
    for row in gold:
        for i, candidate in enumerate(unmatched):
            if _rows_match(row, candidate):
                del unmatched[i]
                break
        else:
            return False
    return True


def results_match(gold_rows: list, pred_rows: list) -> bool:
    gold_rows = [tuple(r) for r in gold_rows]
    pred_rows = [tuple(r) for r in pred_rows]
    if (
        len(gold_rows) > 1
        and len(pred_rows) == 1
        and all(len(r) == 1 for r in gold_rows)
        and len(pred_rows[0]) == len(gold_rows)
    ):
        # Same values laid out as one row instead of one column.
        return _same_rows(gold_rows, [(v,) for v in pred_rows[0]])
    if len(gold_rows) != len(pred_rows):
        return False
    if not gold_rows:
        return True
    gold_width, pred_width = len(gold_rows[0]), len(pred_rows[0])
    if pred_width < gold_width:
        return False

    # For each gold column, the predicted columns holding the same values (in any order).
    candidates = []
    for g in range(gold_width):
        gold_column = [(r[g],) for r in gold_rows]
        matches = [p for p in range(pred_width) if _same_rows(gold_column, [(r[p],) for r in pred_rows])]
        if not matches:
            return False
        candidates.append(matches)

    # Try every way of assigning distinct predicted columns to the gold columns.
    for mapping in permutations(range(pred_width), gold_width):
        if all(mapping[g] in candidates[g] for g in range(gold_width)):
            projected = [tuple(r[p] for p in mapping) for r in pred_rows]
            if _same_rows(gold_rows, projected):
                return True
    return False
