"""Derive integer bounds from a constraint expression via transitive analysis.

Entry points:
    infer_int_bounds(node, constraint) -> dict[str, tuple[int, int]]
    fill_int_bounds(node, bounds) -> IRNode
"""

from __future__ import annotations

from equivalib.core.expression import (
    Expression,
    And,
    Ge,
    Le,
    Gt,
    Lt,
    Eq,
    Reference,
    IntegerConstant,
)
from equivalib.core.types import (
    IRNode,
    NamedNode,
    UnboundedIntNode,
    IntRangeNode,
    TupleNode,
    UnionNode,
)

_INF = float("inf")


def _collect_unbounded_int_labels(node: IRNode) -> frozenset[str]:
    """Return all label names whose inner node is UnboundedIntNode."""
    if isinstance(node, NamedNode):
        if isinstance(node.inner, UnboundedIntNode):
            return frozenset({node.label})
        return _collect_unbounded_int_labels(node.inner)
    if isinstance(node, TupleNode):
        result: frozenset[str] = frozenset()
        for item in node.items:
            result = result | _collect_unbounded_int_labels(item)
        return result
    if isinstance(node, UnionNode):
        result = frozenset()
        for opt in node.options:
            result = result | _collect_unbounded_int_labels(opt)
        return result
    return frozenset()


def _has_cycle_in_rel_lt(
    rel_lt: list[tuple[str, str]], int_labels: frozenset[str]
) -> bool:
    """Return True if the strict-inequality graph contains a directed cycle.

    This detects contradictions such as X < Y and Y < X even when no finite
    bounds are present (where the Bellman-Ford propagation loop would make no
    progress and fall through to the "missing bounds" error instead).
    """
    graph: dict[str, list[str]] = {label: [] for label in int_labels}
    for x, y in rel_lt:
        if x in graph and y in int_labels:
            graph[x].append(y)

    WHITE, GRAY, BLACK = 0, 1, 2
    color: dict[str, int] = {label: WHITE for label in int_labels}

    for start in int_labels:
        if color[start] != WHITE:
            continue
        stack: list[tuple[str, object]] = [(start, iter(graph[start]))]
        color[start] = GRAY
        while stack:
            node, neighbors = stack[-1]
            try:
                neighbor = next(neighbors)  # type: ignore[call-overload]
                if color.get(neighbor, BLACK) == GRAY:
                    return True
                if color.get(neighbor, BLACK) == WHITE:
                    color[neighbor] = GRAY
                    stack.append((neighbor, iter(graph[neighbor])))
            except StopIteration:
                color[node] = BLACK
                stack.pop()

    return False


def _flatten_and(expr: Expression) -> list[Expression]:
    """Return all top-level AND conjuncts from a constraint."""
    result: list[Expression] = []
    stack: list[Expression] = [expr]
    while stack:
        current = stack.pop()
        if isinstance(current, And):
            stack.append(current.right)
            stack.append(current.left)
        else:
            result.append(current)
    return result


def _try_extract_bound(
    expr: Expression,
    int_labels: frozenset[str],
    direct_lo: dict[str, float],
    direct_hi: dict[str, float],
    rel_lt: list[tuple[str, str]],
    rel_le: list[tuple[str, str]],
    rel_eq: list[tuple[str, str]],
) -> None:
    """Extract a bound from a simple comparison conjunct, if possible."""

    def is_plain_ref(e: Expression) -> bool:
        return isinstance(e, Reference) and not e.path and e.label in int_labels

    def is_int_const(e: Expression) -> bool:
        return isinstance(e, IntegerConstant)

    if isinstance(expr, Ge):
        if is_plain_ref(expr.left) and is_int_const(expr.right):
            label = expr.left.label  # type: ignore[union-attr]
            n = expr.right.value  # type: ignore[union-attr]
            direct_lo[label] = max(direct_lo.get(label, -_INF), n)
        elif is_int_const(expr.left) and is_plain_ref(expr.right):
            label = expr.right.label  # type: ignore[union-attr]
            n = expr.left.value  # type: ignore[union-attr]
            direct_hi[label] = min(direct_hi.get(label, _INF), n)
        elif is_plain_ref(expr.left) and is_plain_ref(expr.right):
            lx = expr.left.label  # type: ignore[union-attr]
            ry = expr.right.label  # type: ignore[union-attr]
            rel_le.append((ry, lx))

    elif isinstance(expr, Le):
        if is_plain_ref(expr.left) and is_int_const(expr.right):
            label = expr.left.label  # type: ignore[union-attr]
            n = expr.right.value  # type: ignore[union-attr]
            direct_hi[label] = min(direct_hi.get(label, _INF), n)
        elif is_int_const(expr.left) and is_plain_ref(expr.right):
            label = expr.right.label  # type: ignore[union-attr]
            n = expr.left.value  # type: ignore[union-attr]
            direct_lo[label] = max(direct_lo.get(label, -_INF), n)
        elif is_plain_ref(expr.left) and is_plain_ref(expr.right):
            lx = expr.left.label  # type: ignore[union-attr]
            ry = expr.right.label  # type: ignore[union-attr]
            rel_le.append((lx, ry))

    elif isinstance(expr, Gt):
        if is_plain_ref(expr.left) and is_int_const(expr.right):
            label = expr.left.label  # type: ignore[union-attr]
            n = expr.right.value  # type: ignore[union-attr]
            direct_lo[label] = max(direct_lo.get(label, -_INF), n + 1)
        elif is_int_const(expr.left) and is_plain_ref(expr.right):
            label = expr.right.label  # type: ignore[union-attr]
            n = expr.left.value  # type: ignore[union-attr]
            direct_hi[label] = min(direct_hi.get(label, _INF), n - 1)
        elif is_plain_ref(expr.left) and is_plain_ref(expr.right):
            lx = expr.left.label  # type: ignore[union-attr]
            ry = expr.right.label  # type: ignore[union-attr]
            rel_lt.append((ry, lx))

    elif isinstance(expr, Lt):
        if is_plain_ref(expr.left) and is_int_const(expr.right):
            label = expr.left.label  # type: ignore[union-attr]
            n = expr.right.value  # type: ignore[union-attr]
            direct_hi[label] = min(direct_hi.get(label, _INF), n - 1)
        elif is_int_const(expr.left) and is_plain_ref(expr.right):
            label = expr.right.label  # type: ignore[union-attr]
            n = expr.left.value  # type: ignore[union-attr]
            direct_lo[label] = max(direct_lo.get(label, -_INF), n + 1)
        elif is_plain_ref(expr.left) and is_plain_ref(expr.right):
            lx = expr.left.label  # type: ignore[union-attr]
            ry = expr.right.label  # type: ignore[union-attr]
            rel_lt.append((lx, ry))

    elif isinstance(expr, Eq):
        if is_plain_ref(expr.left) and is_int_const(expr.right):
            label = expr.left.label  # type: ignore[union-attr]
            n = expr.right.value  # type: ignore[union-attr]
            direct_lo[label] = max(direct_lo.get(label, -_INF), n)
            direct_hi[label] = min(direct_hi.get(label, _INF), n)
        elif is_int_const(expr.left) and is_plain_ref(expr.right):
            label = expr.right.label  # type: ignore[union-attr]
            n = expr.left.value  # type: ignore[union-attr]
            direct_lo[label] = max(direct_lo.get(label, -_INF), n)
            direct_hi[label] = min(direct_hi.get(label, _INF), n)
        elif is_plain_ref(expr.left) and is_plain_ref(expr.right):
            lx = expr.left.label  # type: ignore[union-attr]
            ry = expr.right.label  # type: ignore[union-attr]
            rel_eq.append((lx, ry))


def infer_int_bounds(
    node: IRNode,
    constraint: Expression,
) -> dict[str, tuple[int, int]]:
    """Infer lower and upper bounds for each named unbounded integer in the tree."""
    int_labels = _collect_unbounded_int_labels(node)
    if not int_labels:
        return {}

    lo: dict[str, float] = {label: -_INF for label in int_labels}
    hi: dict[str, float] = {label: _INF for label in int_labels}

    direct_lo: dict[str, float] = {}
    direct_hi: dict[str, float] = {}
    rel_lt: list[tuple[str, str]] = []
    rel_le: list[tuple[str, str]] = []
    rel_eq: list[tuple[str, str]] = []

    for conjunct in _flatten_and(constraint):
        _try_extract_bound(conjunct, int_labels, direct_lo, direct_hi, rel_lt, rel_le, rel_eq)

    for label, v in direct_lo.items():
        lo[label] = max(lo[label], v)
    for label, v in direct_hi.items():
        hi[label] = min(hi[label], v)

    # Detect cycles in the strict-inequality graph (e.g. X < Y < X, or X < X).
    # Cycles are contradictions for integers, and must be caught before the
    # fixed-point loop because the loop makes no progress when no finite bounds
    # are present to propagate.
    if any(x == y for (x, y) in rel_lt) or _has_cycle_in_rel_lt(rel_lt, int_labels):
        return {label: (1, 0) for label in int_labels}

    # Propagate bounds to a fixed point.
    changed = True
    while changed:
        changed = False
        for (x, y) in rel_lt:
            if hi[y] != _INF:
                new_x_hi = hi[y] - 1
                if new_x_hi < hi[x]:
                    hi[x] = new_x_hi
                    changed = True
            if lo[x] != -_INF:
                new_y_lo = lo[x] + 1
                if new_y_lo > lo[y]:
                    lo[y] = new_y_lo
                    changed = True

        for (x, y) in rel_le:
            if hi[y] < hi[x]:
                hi[x] = hi[y]
                changed = True
            if lo[x] > lo[y]:
                lo[y] = lo[x]
                changed = True

        for (x, y) in rel_eq:
            new_lo = max(lo[x], lo[y])
            new_hi = min(hi[x], hi[y])
            if new_lo > lo[x] or new_hi < hi[x]:
                lo[x] = new_lo
                hi[x] = new_hi
                changed = True
            if new_lo > lo[y] or new_hi < hi[y]:
                lo[y] = new_lo
                hi[y] = new_hi
                changed = True

        # Short-circuit as soon as any bounds become contradictory (lo > hi).
        # Some unrelated labels may still have ±∞ bounds here, so return an
        # explicit unsatisfiable sentinel instead of converting all bounds to int.
        if any(lo[label] > hi[label] for label in int_labels):
            return {label: (1, 0) for label in int_labels}

    missing: list[str] = []
    for label in sorted(int_labels):
        if lo[label] == -_INF:
            missing.append(f"lower bound for {label!r}")
        if hi[label] == _INF:
            missing.append(f"upper bound for {label!r}")

    if missing:
        raise ValueError(
            f"Could not derive bounds for the following integer labels from the constraint: "
            f"{', '.join(missing)}. "
            "Add explicit bound constraints using Ge, Le, Gt, Lt, or Eq "
            "(e.g. And(Ge(ref('X'), IntegerConstant(0)), Le(ref('X'), IntegerConstant(9))))."
        )

    return {label: (int(lo[label]), int(hi[label])) for label in int_labels}


def fill_int_bounds(node: IRNode, bounds: dict[str, tuple[int, int]]) -> IRNode:
    """Replace every NamedNode(label, UnboundedIntNode()) with NamedNode(label, IntRangeNode(lo, hi))."""
    if isinstance(node, NamedNode):
        if isinstance(node.inner, UnboundedIntNode):
            lo, hi = bounds[node.label]
            return NamedNode(node.label, IntRangeNode(lo, hi))
        new_inner = fill_int_bounds(node.inner, bounds)
        if new_inner is node.inner:
            return node
        return NamedNode(node.label, new_inner)
    if isinstance(node, TupleNode):
        new_items = tuple(fill_int_bounds(item, bounds) for item in node.items)
        if new_items == node.items:
            return node
        return TupleNode(new_items)
    if isinstance(node, UnionNode):
        new_options = tuple(fill_int_bounds(opt, bounds) for opt in node.options)
        if new_options == node.options:
            return node
        return UnionNode(new_options)
    return node
