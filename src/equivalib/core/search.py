"""Satisfying-assignment search — delegates to the CP-SAT backend.

Public API:
    search(node, constraint) -> list[dict]

Each element in the returned list is a dict mapping label -> value,
representing one satisfying assignment.
"""

from __future__ import annotations

from equivalib.core.expression import Expression
from equivalib.core.types import IRNode
from equivalib.core.sat import sat_search


def search(node: IRNode, constraint: Expression) -> list[dict[str, object]]:
    """Return a list of satisfying assignments.

    Delegates to the CP-SAT backend (``sat_search``) which encodes
    boolean and integer-range labels as CP-SAT variables and enumerates
    all solutions via a solution callback.  Labels with other domain types
    (string/None/tuple literals, mixed unions) are enumerated in Python with
    partial-evaluation pruning.
    """
    return sat_search(node, constraint)
