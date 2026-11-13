"""Merge estimated daily rows into a measured series. Measured values always win."""
from __future__ import annotations

from datetime import date
from typing import Iterable, List, Optional, Sequence, Set, Tuple

from rwcwx.estimated.conversions import BLEND

# (var, type) pairs this version can fill.
ESTIMATED_VARS = frozenset(BLEND.keys())


def is_estimated_row(row) -> bool:
    return bool(getattr(row, "is_estimated", False))


def merge_rows(measured: Sequence, estimated: Sequence) -> list:
    """Return measured rows plus estimated days that have no measured value.

    Result is newest-first, matching AvgExtQ.for_var_between_dates.
    """
    have = {row.d for row in measured}
    extra = [row for row in estimated if row.d not in have]
    return sorted(list(measured) + extra, key=lambda row: row.d, reverse=True)


def merge_values(
    measured: Sequence[Tuple[date, float]],
    estimated: Sequence,
) -> List[Tuple[date, float]]:
    """Chronological (date, value) list; measured wins on the same date."""
    have = {d for d, _ in measured}
    extra = [(row.d, row.val) for row in estimated if row.d not in have]
    return sorted(list(measured) + extra, key=lambda item: item[0])


def estimated_dates(estimated: Iterable) -> Set[date]:
    return {row.d for row in estimated}


def span_has_estimated(start, end, dates: Set[date]) -> bool:
    """True if any estimated day falls in [start, end] (inclusive). start/end may be date or (y,m,d)."""
    if not dates:
        return False

    def as_date(x):
        if isinstance(x, date):
            return x
        if isinstance(x, (list, tuple)) and len(x) >= 3:
            return date(int(x[0]), int(x[1]), int(x[2]))
        return None

    a, b = as_date(start), as_date(end)
    if a is None or b is None:
        return False
    if a > b:
        a, b = b, a
    # Fast path: check membership without iterating the whole span when the set is small
    # and the span may be long. Iterate the smaller of the two.
    if (b - a).days + 1 <= len(dates):
        d = a
        while d <= b:
            if d in dates:
                return True
            d = date.fromordinal(d.toordinal() + 1)
        return False
    return any(a <= d <= b for d in dates)


def mark_periods(rows: Optional[list], dates: Set[date], start_key="start", end_key="end") -> Optional[list]:
    """Add est=True to ranking-style rows whose [start, end] overlaps an estimated day."""
    if not rows or not dates:
        return rows
    out = []
    for row in rows:
        if not isinstance(row, dict):
            out.append(row)
            continue
        start = row.get(start_key, row.get("d") or row.get("date"))
        end = row.get(end_key, start)
        if span_has_estimated(start, end, dates):
            marked = dict(row)
            marked["est"] = True
            out.append(marked)
        else:
            out.append(row)
    return out
