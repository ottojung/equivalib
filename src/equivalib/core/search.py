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
from equivalib.core.domains import domain_map
from equivalib.core.order import canonical_sorted
from equivalib.core.eval import eval_expression_partial


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
    try:
        from equivalib.core.sat import sat_search

        return sat_search(node, constraint, methods)
    except ModuleNotFoundError as exc:
        if exc.name != "ortools":
            raise
        return _search_pure_python(node, constraint)


def _search_pure_python(node: IRNode, constraint: Expression) -> list[dict[str, object]]:
    domains = {k: canonical_sorted(v) for k, v in domain_map(node).items()}
    labels = sorted(domains)
    results: list[dict[str, object]] = []

    def backtrack(i: int, current: dict[str, object]) -> None:
        partial = eval_expression_partial(constraint, current)
        if partial is False:
            return
        if i == len(labels):
            if partial is True:
                results.append(dict(current))
            return
        label = labels[i]
        for value in domains[label]:
            current[label] = value
            backtrack(i + 1, current)
        del current[label]

    backtrack(0, {})
    return results
