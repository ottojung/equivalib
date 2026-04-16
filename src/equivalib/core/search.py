"""Satisfying-assignment search — delegates to the CP-SAT backend.

Public API:
    search(node, constraint, methods) -> list[dict]

Each element in the returned list is a dict mapping label -> value,
representing one satisfying assignment.
"""

from __future__ import annotations

from typing import Mapping

from equivalib.core.expression import Expression
from equivalib.core.types import IRNode
from equivalib.core.sat import sat_search


def search(
    node: IRNode,
    constraint: Expression,
    methods: Mapping[str, str] | None = None,
) -> list[dict[str, object]]:
    """Return a list of satisfying assignments.

    Delegates to the CP-SAT backend (``sat_search``) which encodes
    boolean and integer-range labels as CP-SAT variables.  When
    ``methods`` indicates that every label (SAT and enum alike) uses
    ``"arbitrary"``, SAT solution enumeration per enum branch is
    replaced by sequential minimization (one solver call per SAT label
    per branch) rather than enumerating all CP-SAT solutions per branch.
    Full enumeration is performed when any label — SAT or enum — has
    method ``"all"`` or ``"uniform_random"``, because
    ``"uniform_random"`` weighting requires correct per-value
    multiplicity counts from the full satisfying-assignment set.
    Labels with other domain types (string/None/tuple literals, mixed
    unions) are enumerated in Python with partial-evaluation pruning.
    """
    return sat_search(node, constraint, methods)
