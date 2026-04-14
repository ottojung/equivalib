"""Canonical total order on runtime values.

Kind rank table (documented here):
    0 – None
    1 – bool  (True before False: True=1, False=0, so descending)
    2 – int
    3 – str
    4 – tuple

For booleans: True (rank 0) < False (rank 1) means True sorts first.
For all others: natural ascending order within each kind.
"""

from __future__ import annotations

from typing import Any


_KIND_RANK = {
    type(None): 0,
    bool: 1,
    int: 2,
    str: 3,
    tuple: 4,
}


def _kind_rank(v: Any) -> int:
    t = type(v)
    if t in _KIND_RANK:
        return _KIND_RANK[t]
    # Fallback: put unknown types last.
    return 99


def _sort_key(v: Any) -> tuple[Any, ...]:
    """Return a sort key for ``v`` compatible with the canonical total order."""
    rank = _kind_rank(v)
    if v is None:
        return (rank,)
    if isinstance(v, bool):
        # True before False: use 0 for True, 1 for False
        return (rank, 0 if v else 1)
    if isinstance(v, int):
        return (rank, v)
    if isinstance(v, str):
        return (rank, v)
    if isinstance(v, tuple):
        return (rank,) + tuple(_sort_key(e) for e in v)
    return (rank, repr(v))


def canonical_sorted(values: Any) -> list[Any]:
    """Return a list of ``values`` sorted in canonical order."""
    return sorted(values, key=_sort_key)


def canonical_first(values: Any) -> Any:
    """Return the canonical-first element from ``values``."""
    return min(values, key=_sort_key)
