"""Exact backtracking satisfying-assignment search.

Public API:
    search(node, constraint) -> list[dict]

Each element in the returned list is a dict mapping label -> value,
representing one satisfying assignment.
"""

from __future__ import annotations

from equivalib.core.types import labels as tree_labels
from equivalib.core.domains import domain_map
from equivalib.core.order import canonical_sorted
from equivalib.core.eval import eval_expression_partial


def search(node: object, constraint: object) -> list:
    """Return a list of satisfying assignments.

    Each assignment is a dict mapping label -> value.
    Labels are assigned in ascending lexicographic order.
    Domain values are iterated in canonical value order.
    Partial-evaluation pruning eliminates dead branches early.
    """
    label_list = sorted(tree_labels(node))
    domains = domain_map(node)

    # Early exit: any empty domain means no satisfying assignments exist.
    for d in domains.values():
        if not d:
            return []

    results: list = []
    _backtrack(label_list, domains, constraint, {}, results)
    return results


def _backtrack(
    label_list: list,
    domains: dict,
    constraint: object,
    partial: dict,
    results: list,
) -> None:
    if not label_list:
        # All labels assigned; the constraint must evaluate to exactly True.
        result = eval_expression_partial(constraint, partial)
        if result is True:
            results.append(dict(partial))
        return

    label = label_list[0]
    rest = label_list[1:]
    domain = domains.get(label, frozenset())

    for value in canonical_sorted(domain):
        partial[label] = value
        # Partial pruning: if constraint is already False, skip this branch.
        result = eval_expression_partial(constraint, partial)
        if result is not False:
            _backtrack(rest, domains, constraint, partial, results)
        del partial[label]
