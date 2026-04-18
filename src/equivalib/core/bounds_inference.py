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

def _max_bound(a: int | None, b: int | None) -> int | None:
    """Return the tighter lower bound (max), treating None as −∞."""
    if a is None:
        return b
    if b is None:
        return a
    return max(a, b)


def _min_bound(a: int | None, b: int | None) -> int | None:
    """Return the tighter upper bound (min), treating None as +∞."""
    if a is None:
        return b
    if b is None:
        return a
    return min(a, b)


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
    direct_lo: dict[str, int],
    direct_hi: dict[str, int],
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
            direct_lo[label] = n if label not in direct_lo else max(direct_lo[label], n)
        elif is_int_const(expr.left) and is_plain_ref(expr.right):
            label = expr.right.label  # type: ignore[union-attr]
            n = expr.left.value  # type: ignore[union-attr]
            direct_hi[label] = n if label not in direct_hi else min(direct_hi[label], n)
        elif is_plain_ref(expr.left) and is_plain_ref(expr.right):
            lx = expr.left.label  # type: ignore[union-attr]
            ry = expr.right.label  # type: ignore[union-attr]
            rel_le.append((ry, lx))

    elif isinstance(expr, Le):
        if is_plain_ref(expr.left) and is_int_const(expr.right):
            label = expr.left.label  # type: ignore[union-attr]
            n = expr.right.value  # type: ignore[union-attr]
            direct_hi[label] = n if label not in direct_hi else min(direct_hi[label], n)
        elif is_int_const(expr.left) and is_plain_ref(expr.right):
            label = expr.right.label  # type: ignore[union-attr]
            n = expr.left.value  # type: ignore[union-attr]
            direct_lo[label] = n if label not in direct_lo else max(direct_lo[label], n)
        elif is_plain_ref(expr.left) and is_plain_ref(expr.right):
            lx = expr.left.label  # type: ignore[union-attr]
            ry = expr.right.label  # type: ignore[union-attr]
            rel_le.append((lx, ry))

    elif isinstance(expr, Gt):
        if is_plain_ref(expr.left) and is_int_const(expr.right):
            label = expr.left.label  # type: ignore[union-attr]
            n = expr.right.value  # type: ignore[union-attr]
            direct_lo[label] = n + 1 if label not in direct_lo else max(direct_lo[label], n + 1)
        elif is_int_const(expr.left) and is_plain_ref(expr.right):
            label = expr.right.label  # type: ignore[union-attr]
            n = expr.left.value  # type: ignore[union-attr]
            direct_hi[label] = n - 1 if label not in direct_hi else min(direct_hi[label], n - 1)
        elif is_plain_ref(expr.left) and is_plain_ref(expr.right):
            lx = expr.left.label  # type: ignore[union-attr]
            ry = expr.right.label  # type: ignore[union-attr]
            rel_lt.append((ry, lx))

    elif isinstance(expr, Lt):
        if is_plain_ref(expr.left) and is_int_const(expr.right):
            label = expr.left.label  # type: ignore[union-attr]
            n = expr.right.value  # type: ignore[union-attr]
            direct_hi[label] = n - 1 if label not in direct_hi else min(direct_hi[label], n - 1)
        elif is_int_const(expr.left) and is_plain_ref(expr.right):
            label = expr.right.label  # type: ignore[union-attr]
            n = expr.left.value  # type: ignore[union-attr]
            direct_lo[label] = n + 1 if label not in direct_lo else max(direct_lo[label], n + 1)
        elif is_plain_ref(expr.left) and is_plain_ref(expr.right):
            lx = expr.left.label  # type: ignore[union-attr]
            ry = expr.right.label  # type: ignore[union-attr]
            rel_lt.append((lx, ry))

    elif isinstance(expr, Eq):
        if is_plain_ref(expr.left) and is_int_const(expr.right):
            label = expr.left.label  # type: ignore[union-attr]
            n = expr.right.value  # type: ignore[union-attr]
            direct_lo[label] = n if label not in direct_lo else max(direct_lo[label], n)
            direct_hi[label] = n if label not in direct_hi else min(direct_hi[label], n)
        elif is_int_const(expr.left) and is_plain_ref(expr.right):
            label = expr.right.label  # type: ignore[union-attr]
            n = expr.left.value  # type: ignore[union-attr]
            direct_lo[label] = n if label not in direct_lo else max(direct_lo[label], n)
            direct_hi[label] = n if label not in direct_hi else min(direct_hi[label], n)
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

    # None means "unbounded" (lo: −∞, hi: +∞). Using int|None avoids float
    # arithmetic entirely, which preserves precision for large integer constants.
    lo: dict[str, int | None] = {label: None for label in int_labels}
    hi: dict[str, int | None] = {label: None for label in int_labels}

    direct_lo: dict[str, int] = {}
    direct_hi: dict[str, int] = {}
    rel_lt: list[tuple[str, str]] = []
    rel_le: list[tuple[str, str]] = []
    rel_eq: list[tuple[str, str]] = []

    for conjunct in _flatten_and(constraint):
        _try_extract_bound(conjunct, int_labels, direct_lo, direct_hi, rel_lt, rel_le, rel_eq)

    for label, v in direct_lo.items():
        lo[label] = _max_bound(lo[label], v)
    for label, v in direct_hi.items():
        hi[label] = _min_bound(hi[label], v)

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
            hi_y = hi[y]
            if hi_y is not None:
                new_x_hi = hi_y - 1
                hi_x = hi[x]
                if hi_x is None or new_x_hi < hi_x:
                    hi[x] = new_x_hi
                    changed = True
            lo_x = lo[x]
            if lo_x is not None:
                new_y_lo = lo_x + 1
                lo_y = lo[y]
                if lo_y is None or new_y_lo > lo_y:
                    lo[y] = new_y_lo
                    changed = True

        for (x, y) in rel_le:
            new_hx = _min_bound(hi[x], hi[y])
            if new_hx != hi[x]:
                hi[x] = new_hx
                changed = True
            new_ly = _max_bound(lo[y], lo[x])
            if new_ly != lo[y]:
                lo[y] = new_ly
                changed = True

        for (x, y) in rel_eq:
            new_lo = _max_bound(lo[x], lo[y])
            new_hi = _min_bound(hi[x], hi[y])
            if new_lo != lo[x] or new_hi != hi[x]:
                lo[x] = new_lo
                hi[x] = new_hi
                changed = True
            if new_lo != lo[y] or new_hi != hi[y]:
                lo[y] = new_lo
                hi[y] = new_hi
                changed = True

        # Short-circuit as soon as any bounds become contradictory (lo > hi).
        # Some unrelated labels may still have no bounds here, so return an
        # explicit unsatisfiable sentinel instead of propagating further.
        for label in int_labels:
            lo_v, hi_v = lo[label], hi[label]
            if lo_v is not None and hi_v is not None and lo_v > hi_v:
                return {label: (1, 0) for label in int_labels}

    missing: list[str] = []
    for label in sorted(int_labels):
        if lo[label] is None:
            missing.append(f"lower bound for {label!r}")
        if hi[label] is None:
            missing.append(f"upper bound for {label!r}")

    if missing:
        raise ValueError(
            f"Could not derive bounds for the following integer labels from the constraint: "
            f"{', '.join(missing)}. "
            "Add explicit bound constraints using Ge, Le, Gt, Lt, or Eq "
            "(e.g. And(Ge(ref('X'), IntegerConstant(0)), Le(ref('X'), IntegerConstant(9))))."
        )

    # At this point all bounds are confirmed non-None (missing is empty).
    result: dict[str, tuple[int, int]] = {}
    for label in int_labels:
        lo_v = lo[label]
        hi_v = hi[label]
        assert lo_v is not None and hi_v is not None  # guaranteed by missing-check above
        result[label] = (lo_v, hi_v)
    return result


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
