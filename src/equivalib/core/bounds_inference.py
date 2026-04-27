"""Derive integer bounds from a constraint expression via transitive analysis.

Entry points:
    infer_int_bounds(node, constraint) -> dict[RefKey, tuple[int, int]]
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

RefKey = tuple[str | None, tuple[int, ...]]


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


def _collect_unbounded_int_ref_keys(node: IRNode) -> frozenset[RefKey]:
    """Return all ``(label, path)`` references that point to unbounded ints."""

    def walk(n: IRNode, current_label: str | None, prefix: tuple[int, ...]) -> frozenset[RefKey]:
        if isinstance(n, UnboundedIntNode):
            return frozenset({(current_label, prefix)})
        if isinstance(n, NamedNode):
            return walk(n.inner, n.label, ())
        if isinstance(n, TupleNode):
            result: frozenset[RefKey] = frozenset()
            for idx, item in enumerate(n.items):
                result = result | walk(item, current_label, prefix + (idx,))
            return result
        if isinstance(n, UnionNode):
            result = frozenset()
            for opt in n.options:
                result = result | walk(opt, current_label, prefix)
            return result
        return frozenset()

    return walk(node, None, ())


def _has_cycle_in_rel_lt(
    rel_lt: list[tuple[RefKey, RefKey]], int_refs: frozenset[RefKey]
) -> bool:
    """Return True if the strict-inequality graph contains a directed cycle.

    This detects contradictions such as X < Y and Y < X even when no finite
    bounds are present (where the Bellman-Ford propagation loop would make no
    progress and fall through to the "missing bounds" error instead).
    """
    graph: dict[RefKey, list[RefKey]] = {key: [] for key in int_refs}
    for x, y in rel_lt:
        if x in graph and y in int_refs:
            graph[x].append(y)

    WHITE, GRAY, BLACK = 0, 1, 2
    color: dict[RefKey, int] = {key: WHITE for key in int_refs}

    for start in int_refs:
        if color[start] != WHITE:
            continue
        stack: list[tuple[RefKey, object]] = [(start, iter(graph[start]))]
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
    int_refs: frozenset[RefKey],
    direct_lo: dict[RefKey, int],
    direct_hi: dict[RefKey, int],
    rel_lt: list[tuple[RefKey, RefKey]],
    rel_le: list[tuple[RefKey, RefKey]],
    rel_eq: list[tuple[RefKey, RefKey]],
) -> None:
    """Extract a bound from a simple comparison conjunct, if possible."""

    def ref_key(e: Expression) -> RefKey | None:
        if not isinstance(e, Reference):
            return None
        key = (e.label, e.path)
        if key not in int_refs:
            return None
        return key

    def is_int_const(e: Expression) -> bool:
        return isinstance(e, IntegerConstant)

    if isinstance(expr, Ge):
        left_key = ref_key(expr.left)
        right_key = ref_key(expr.right)
        if left_key is not None and is_int_const(expr.right):
            n = expr.right.value  # type: ignore[union-attr]
            direct_lo[left_key] = n if left_key not in direct_lo else max(direct_lo[left_key], n)
        elif is_int_const(expr.left) and right_key is not None:
            n = expr.left.value  # type: ignore[union-attr]
            direct_hi[right_key] = n if right_key not in direct_hi else min(direct_hi[right_key], n)
        elif left_key is not None and right_key is not None:
            rel_le.append((right_key, left_key))

    elif isinstance(expr, Le):
        left_key = ref_key(expr.left)
        right_key = ref_key(expr.right)
        if left_key is not None and is_int_const(expr.right):
            n = expr.right.value  # type: ignore[union-attr]
            direct_hi[left_key] = n if left_key not in direct_hi else min(direct_hi[left_key], n)
        elif is_int_const(expr.left) and right_key is not None:
            n = expr.left.value  # type: ignore[union-attr]
            direct_lo[right_key] = n if right_key not in direct_lo else max(direct_lo[right_key], n)
        elif left_key is not None and right_key is not None:
            rel_le.append((left_key, right_key))

    elif isinstance(expr, Gt):
        left_key = ref_key(expr.left)
        right_key = ref_key(expr.right)
        if left_key is not None and is_int_const(expr.right):
            n = expr.right.value  # type: ignore[union-attr]
            direct_lo[left_key] = n + 1 if left_key not in direct_lo else max(direct_lo[left_key], n + 1)
        elif is_int_const(expr.left) and right_key is not None:
            n = expr.left.value  # type: ignore[union-attr]
            direct_hi[right_key] = n - 1 if right_key not in direct_hi else min(direct_hi[right_key], n - 1)
        elif left_key is not None and right_key is not None:
            rel_lt.append((right_key, left_key))

    elif isinstance(expr, Lt):
        left_key = ref_key(expr.left)
        right_key = ref_key(expr.right)
        if left_key is not None and is_int_const(expr.right):
            n = expr.right.value  # type: ignore[union-attr]
            direct_hi[left_key] = n - 1 if left_key not in direct_hi else min(direct_hi[left_key], n - 1)
        elif is_int_const(expr.left) and right_key is not None:
            n = expr.left.value  # type: ignore[union-attr]
            direct_lo[right_key] = n + 1 if right_key not in direct_lo else max(direct_lo[right_key], n + 1)
        elif left_key is not None and right_key is not None:
            rel_lt.append((left_key, right_key))

    elif isinstance(expr, Eq):
        left_key = ref_key(expr.left)
        right_key = ref_key(expr.right)
        if left_key is not None and is_int_const(expr.right):
            n = expr.right.value  # type: ignore[union-attr]
            direct_lo[left_key] = n if left_key not in direct_lo else max(direct_lo[left_key], n)
            direct_hi[left_key] = n if left_key not in direct_hi else min(direct_hi[left_key], n)
        elif is_int_const(expr.left) and right_key is not None:
            n = expr.left.value  # type: ignore[union-attr]
            direct_lo[right_key] = n if right_key not in direct_lo else max(direct_lo[right_key], n)
            direct_hi[right_key] = n if right_key not in direct_hi else min(direct_hi[right_key], n)
        elif left_key is not None and right_key is not None:
            rel_eq.append((left_key, right_key))


def infer_int_bounds(
    node: IRNode,
    constraint: Expression,
) -> dict[RefKey, tuple[int, int]]:
    """Infer lower and upper bounds for each addressable unbounded integer in the tree."""
    int_refs = _collect_unbounded_int_ref_keys(node)
    if not int_refs:
        return {}

    # None means "unbounded" (lo: −∞, hi: +∞). Using int|None avoids float
    # arithmetic entirely, which preserves precision for large integer constants.
    lo: dict[RefKey, int | None] = {key: None for key in int_refs}
    hi: dict[RefKey, int | None] = {key: None for key in int_refs}

    direct_lo: dict[RefKey, int] = {}
    direct_hi: dict[RefKey, int] = {}
    rel_lt: list[tuple[RefKey, RefKey]] = []
    rel_le: list[tuple[RefKey, RefKey]] = []
    rel_eq: list[tuple[RefKey, RefKey]] = []

    for conjunct in _flatten_and(constraint):
        _try_extract_bound(conjunct, int_refs, direct_lo, direct_hi, rel_lt, rel_le, rel_eq)

    for label, v in direct_lo.items():
        lo[label] = _max_bound(lo[label], v)
    for label, v in direct_hi.items():
        hi[label] = _min_bound(hi[label], v)

    # Detect cycles in the strict-inequality graph (e.g. X < Y < X, or X < X).
    # Cycles are contradictions for integers, and must be caught before the
    # fixed-point loop because the loop makes no progress when no finite bounds
    # are present to propagate.
    if any(x == y for (x, y) in rel_lt) or _has_cycle_in_rel_lt(rel_lt, int_refs):
        return {key: (1, 0) for key in int_refs}

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
        for key in int_refs:
            lo_v, hi_v = lo[key], hi[key]
            if lo_v is not None and hi_v is not None and lo_v > hi_v:
                return {rkey: (1, 0) for rkey in int_refs}

    missing: list[str] = []
    for label, path in sorted(int_refs, key=lambda k: (repr(k[0]), k[1])):
        target = f"{label!r}{path!r}"
        if lo[(label, path)] is None:
            missing.append(f"lower bound for {target}")
        if hi[(label, path)] is None:
            missing.append(f"upper bound for {target}")

    if missing:
        raise ValueError(
            f"Could not derive bounds for the following integer references from the constraint: "
            f"{', '.join(missing)}. "
            "Add explicit bound constraints using Ge, Le, Gt, Lt, or Eq "
            "(e.g. And(Ge(ref('X'), IntegerConstant(0)), Le(ref('X'), IntegerConstant(9))) "
            "or using address paths like reference('T', 0) or reference(0))."
        )

    # At this point all bounds are confirmed non-None (missing is empty).
    result: dict[RefKey, tuple[int, int]] = {}
    for key in int_refs:
        lo_v = lo[key]
        hi_v = hi[key]
        assert lo_v is not None and hi_v is not None  # guaranteed by missing-check above
        result[key] = (lo_v, hi_v)
    return result


def fill_int_bounds(node: IRNode, bounds: dict[RefKey, tuple[int, int]]) -> IRNode:
    """Replace every addressable ``UnboundedIntNode`` with the inferred ``IntRangeNode``."""

    def fill(n: IRNode, current_label: str | None, path: tuple[int, ...]) -> IRNode:
        if isinstance(n, NamedNode):
            new_inner = fill(n.inner, n.label, ())
            if new_inner is n.inner:
                return n
            return NamedNode(n.label, new_inner)
        if isinstance(n, UnboundedIntNode):
            lo, hi = bounds[(current_label, path)]
            return IntRangeNode(lo, hi)
        if isinstance(n, TupleNode):
            new_items = tuple(fill(item, current_label, path + (idx,)) for idx, item in enumerate(n.items))
            if new_items == n.items:
                return n
            return TupleNode(new_items)
        if isinstance(n, UnionNode):
            new_options = tuple(fill(opt, current_label, path) for opt in n.options)
            if new_options == n.options:
                return n
            return UnionNode(new_options)
        return n

    filled = fill(node, None, ())
    if isinstance(node, NamedNode):
        # keep static type narrow for callers
        return filled
    if isinstance(node, TupleNode):
        return filled
    if isinstance(node, UnionNode):
        return filled
    return filled
