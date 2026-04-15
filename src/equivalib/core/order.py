"""Canonical total order on runtime values.

Kind rank table (documented here):
    0 – None
    1 – bool
    2 – int
    3 – str
    4 – tuple

Within each kind, ascending order is used.  For booleans the secondary key
is ``0`` for ``True`` and ``1`` for ``False``, so ``True`` sorts before
``False``.  For all other kinds: natural ascending order.
"""

from __future__ import annotations

from typing import Iterable


_KIND_RANK = {
    type(None): 0,
    bool: 1,
    int: 2,
    str: 3,
    tuple: 4,
}


def _kind_rank(v: object) -> int:
    t = type(v)
    if t in _KIND_RANK:
        return _KIND_RANK[t]
    # Fallback: put unknown types last.
    return 99


def _sort_key(v: object) -> tuple[object, ...]:
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


def canonical_sorted(values: Iterable[object]) -> list[object]:
    """Return a list of ``values`` sorted in canonical order."""
    return sorted(values, key=_sort_key)


def canonical_first(values: Iterable[object]) -> object:
    """Return the canonical-first element from ``values``."""
    return min(values, key=_sort_key)
