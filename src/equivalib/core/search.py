"""Exact backtracking satisfying-assignment search.

Public API:
    search(node, constraint) -> list[dict]

Each element in the returned list is a dict mapping label -> value,
representing one satisfying assignment.
"""

from __future__ import annotations

from equivalib.core.expression import Expression
from equivalib.core.types import IRNode, labels as tree_labels
from equivalib.core.domains import domain_map
from equivalib.core.order import canonical_sorted
from equivalib.core.eval import eval_expression_partial


def search(node: IRNode, constraint: Expression) -> list[dict[str, object]]:
    """Return a list of satisfying assignments.

    Each assignment is a dict mapping label -> value.
    Labels are assigned in ascending lexicographic order.
    Domain values are iterated in canonical value order.
    Partial-evaluation pruning eliminates dead branches early.
    """
    label_list = sorted(tree_labels(node))
    domains: dict[str, list[object]] = domain_map(node)

    # Precompute canonical-sorted domain lists once to avoid O(n log n) work
    # on every recursive call inside _backtrack.
    sorted_domains: dict[str, list[object]] = {
        label: canonical_sorted(domains.get(label, []))
        for label in label_list
    }

    # Early exit: any empty domain means no satisfying assignments exist.
    for values in sorted_domains.values():
        if not values:
            return []

    results: list[dict[str, object]] = []
    _backtrack(label_list, sorted_domains, constraint, {}, results)
    return results


def _backtrack(
    label_list: list[str],
    sorted_domains: dict[str, list[object]],
    constraint: Expression,
    partial: dict[str, object],
    results: list[dict[str, object]],
) -> None:
    if not label_list:
        # All labels assigned; the constraint must evaluate to exactly True.
        result = eval_expression_partial(constraint, partial)
        if result is True:
            results.append(dict(partial))
        return

    label = label_list[0]
    rest = label_list[1:]

    for value in sorted_domains.get(label, []):
        partial[label] = value
        # Partial pruning: if constraint is already False, skip this branch.
        result = eval_expression_partial(constraint, partial)
        if result is not False:
            _backtrack(rest, sorted_domains, constraint, partial, results)
        del partial[label]
