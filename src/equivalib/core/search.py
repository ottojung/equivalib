from __future__ import annotations

from typing import Mapping

from equivalib.core.expression import Expression
from equivalib.core.types import IRNode
from equivalib.core.sat import _sat_search_extended


def search(
    node: IRNode,
    constraint: Expression,
    methods: Mapping[str, str] | None = None,
    extensions: dict[type, object] | None = None,
) -> tuple[list[dict[str, object]], dict[str, tuple[object, object]]]:
    """Return ``(assignments, arbitrary_infinite)`` from the CP-SAT backend.

    Delegates to ``_sat_search_extended`` which encodes boolean and
    integer-range labels as CP-SAT variables.  When ``methods`` indicates
    that every label (SAT and enum alike) uses ``"arbitrary"``, SAT solution
    enumeration per enum branch is replaced by sequential minimization (one
    solver call per SAT label per branch) rather than enumerating all CP-SAT
    solutions per branch.  Full enumeration is performed when any label — SAT
    or enum — has method ``"all"`` or ``"uniform_random"``.
    Labels with other domain types (string/None/tuple literals, mixed
    unions) are enumerated in Python with partial-evaluation pruning.
    """
    return _sat_search_extended(node, constraint, methods, extensions)
