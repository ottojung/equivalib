"""Static validators for trees, methods, and expressions.

Three public entry points:
    validate_tree(node)
    validate_methods(node, methods)
    validate_expression(expr, node)
"""

from __future__ import annotations

from typing import Mapping, TypeAlias

from equivalib.core.types import (
    NoneNode,
    BoolNode,
    LiteralNode,
    IntRangeNode,
    TupleNode,
    UnionNode,
    NamedNode,
    labels as tree_labels,
    tree_shape,
)
from equivalib.core.expression import (
    BooleanConstant,
    IntegerConstant,
    Reference,
    Neg,
    Add,
    Sub,
    Mul,
    FloorDiv,
    Mod,
    Eq,
    Ne,
    Lt,
    Le,
    Gt,
    Ge,
    And,
    Or,
)

_VALID_METHODS = frozenset({"all", "arbitrary", "uniform_random", "arbitrarish_randomish"})
LabelShapes: TypeAlias = dict[str, object]
ExprType: TypeAlias = str


def validate_tree(node: object) -> None:
    """Raise ValueError if the IR node tree contains structural problems."""
    _check_node(node)


def _check_node(node: object) -> None:
    if isinstance(node, NoneNode):
        return
    if isinstance(node, BoolNode):
        return
    if isinstance(node, LiteralNode):
        return
    if isinstance(node, IntRangeNode):
        if node.min_value > node.max_value:
            raise ValueError(
                f"IntRangeNode has invalid bounds: {node.min_value} > {node.max_value}."
            )
        return
    if isinstance(node, TupleNode):
        for item in node.items:
            _check_node(item)
        return
    if isinstance(node, UnionNode):
        for opt in node.options:
            _check_node(opt)
        return
    if isinstance(node, NamedNode):
        if node.label == "":
            raise ValueError("Name label must not be empty.")
        _check_node(node.inner)
        return
    raise TypeError(f"Unknown IR node type: {type(node)}")


def validate_methods(node: object, methods: Mapping[str, str]) -> None:
    """Raise ValueError if any method key or value is invalid."""
    known_labels = tree_labels(node)
    for key, method in methods.items():
        if key not in known_labels:
            raise ValueError(
                f"Method key {key!r} is not a label in the tree. "
                f"Known labels: {sorted(known_labels)!r}."
            )
        if method not in _VALID_METHODS:
            raise ValueError(
                f"Unknown method {method!r} for label {key!r}. "
                f"Valid methods are: {sorted(_VALID_METHODS)!r}."
            )


def validate_expression(expr: object, node: object) -> None:
    """Raise ValueError/TypeError if the expression is invalid against the tree.

    Checks:
    - every referenced label exists in the tree
    - every address path is statically valid
    - the top-level expression is boolean
    - numeric operations have numeric operands, etc.
    """
    known_labels = tree_labels(node)

    # Build a label -> shape map for address validation
    label_shapes = _collect_label_shapes(node)

    # Type-check the top-level expression: must be boolean-typed
    result_type = _check_expr_type(expr, known_labels, label_shapes)
    if result_type != "bool":
        raise TypeError(
            f"Top-level constraint must be a boolean expression, "
            f"got {result_type!r}: {expr!r}."
        )


def _collect_label_shapes(node: object) -> LabelShapes:
    """Return a mapping {label: shape_node} for all named nodes in the tree."""
    result: LabelShapes = {}
    _walk_for_shapes(node, result)
    return result


def _walk_for_shapes(node: object, result: LabelShapes) -> None:
    if isinstance(node, (NoneNode, BoolNode, LiteralNode, IntRangeNode)):
        return
    if isinstance(node, TupleNode):
        for item in node.items:
            _walk_for_shapes(item, result)
    elif isinstance(node, UnionNode):
        for opt in node.options:
            _walk_for_shapes(opt, result)
    elif isinstance(node, NamedNode):
        shape = tree_shape(node.inner)
        if node.label in result:
            result[node.label] = _merge_shapes(result[node.label], shape)
        else:
            result[node.label] = shape
        _walk_for_shapes(node.inner, result)


def _merge_shapes(left: object, right: object) -> object:
    """Combine two shapes for repeated-label occurrences."""
    if left == right:
        return left
    options: list[object] = []
    if isinstance(left, UnionNode):
        options.extend(left.options)
    else:
        options.append(left)
    if isinstance(right, UnionNode):
        options.extend(right.options)
    else:
        options.append(right)
    # De-duplicate while preserving order.
    dedup: list[object] = []
    seen: set[object] = set()
    for opt in options:
        if opt not in seen:
            seen.add(opt)
            dedup.append(opt)
    return UnionNode(tuple(dedup))


def _check_expr_type(expr: object, known_labels: frozenset[str], label_shapes: LabelShapes) -> ExprType:
    """Return 'bool', 'numeric', or 'any' (or raise if invalid).

    'any' is returned only for references to labels with opaque shapes
    (e.g. tuples or heterogeneous unions).  The top-level caller rejects 'any'
    at the constraint root; And/Or also reject operands typed as 'any'.
    """
    if isinstance(expr, BooleanConstant):
        return "bool"

    if isinstance(expr, IntegerConstant):
        return "numeric"

    if isinstance(expr, Reference):
        if expr.label not in known_labels:
            raise ValueError(
                f"Reference to unknown label {expr.label!r}. "
                f"Known labels: {sorted(known_labels)!r}."
            )
        if expr.label in label_shapes:
            _validate_address(expr.label, expr.path, label_shapes[expr.label])
            resolved = _resolve_shape(label_shapes[expr.label], expr.path)
            return _shape_type(resolved)
        elif expr.path:
            raise ValueError(
                f"Label {expr.label!r} is not in label_shapes but has a non-empty path."
            )
        return "any"

    if isinstance(expr, Neg):
        t = _check_expr_type(expr.operand, known_labels, label_shapes)
        if t != "numeric":
            raise TypeError(f"Neg operand must be numeric, got {t!r}: {expr!r}")
        return "numeric"

    if isinstance(expr, (Add, Sub, Mul, FloorDiv, Mod)):
        lt = _check_expr_type(expr.left, known_labels, label_shapes)
        rt = _check_expr_type(expr.right, known_labels, label_shapes)
        if lt != "numeric" or rt != "numeric":
            raise TypeError(f"Arithmetic operands must be numeric, got ({lt!r}, {rt!r}): {expr!r}")
        return "numeric"

    if isinstance(expr, (Eq, Ne)):
        _check_expr_type(expr.left, known_labels, label_shapes)
        _check_expr_type(expr.right, known_labels, label_shapes)
        return "bool"

    if isinstance(expr, (Lt, Le, Gt, Ge)):
        lt = _check_expr_type(expr.left, known_labels, label_shapes)
        rt = _check_expr_type(expr.right, known_labels, label_shapes)
        if lt != "numeric" or rt != "numeric":
            raise TypeError(f"Ordering operands must be numeric, got ({lt!r}, {rt!r}): {expr!r}")
        return "bool"

    if isinstance(expr, (And, Or)):
        lt = _check_expr_type(expr.left, known_labels, label_shapes)
        rt = _check_expr_type(expr.right, known_labels, label_shapes)
        if lt != "bool":
            raise TypeError(f"{type(expr).__name__} left operand must be boolean, got {lt!r}: {expr!r}")
        if rt != "bool":
            raise TypeError(f"{type(expr).__name__} right operand must be boolean, got {rt!r}: {expr!r}")
        return "bool"

    # Anything that is not an Expression node is a type error.
    raise TypeError(
        f"Expression must be an AST node, got {type(expr).__name__!r}: {expr!r}"
    )


def _resolve_shape(shape: object, path: tuple[int, ...]) -> object:
    """Navigate ``shape`` by following ``path`` and return the resulting sub-shape.

    When traversing through a ``UnionNode``, all branches are visited and the
    results are combined: if all branches yield the same shape, that shape is
    returned directly; otherwise a new ``UnionNode`` of the resolved sub-shapes
    is returned so that ``_shape_type`` can unify the types.
    """
    if not path:
        return shape
    idx = path[0]
    remaining = path[1:]

    if isinstance(shape, UnionNode):
        # _validate_address already ensured all options are TupleNodes with
        # valid indices; navigate each branch and collect sub-shapes.
        collected: list[object] = []
        for opt in shape.options:
            if not isinstance(opt, TupleNode):
                raise ValueError(
                    f"Cannot index into non-tuple union option {opt!r} at path {path!r}."
                )
            collected.append(_resolve_shape(opt.items[idx], remaining))
        sub_shapes = tuple(collected)
        # If all branches resolve to the same shape, return it directly.
        if len(set(sub_shapes)) == 1:
            return sub_shapes[0]
        return UnionNode(sub_shapes)

    if isinstance(shape, TupleNode):
        return _resolve_shape(shape.items[idx], remaining)

    raise ValueError(f"Cannot index into shape {shape!r} at path {path!r}.")


def _shape_type(shape: object) -> str:
    """Return the expression type ('bool', 'numeric', or 'any') for a given shape."""
    if isinstance(shape, BoolNode):
        return "bool"
    if isinstance(shape, IntRangeNode):
        return "numeric"
    if isinstance(shape, LiteralNode):
        # Infer from the literal value's Python type.
        if isinstance(shape.value, bool):
            return "bool"
        if isinstance(shape.value, int):
            return "numeric"
        return "any"
    if isinstance(shape, UnionNode):
        option_types = {_shape_type(o) for o in shape.options}
        if len(option_types) == 1:
            return option_types.pop()
        return "any"
    # NoneNode, TupleNode, etc. are opaque in expression context.
    return "any"


def _validate_address(label: str, path: tuple[int, ...], shape: object) -> None:
    """Raise ValueError if ``path`` is not a valid address into ``shape``."""
    _validate_address_from(label, path, shape, 0)


def _validate_address_from(label: str, path: tuple[int, ...], current: object, position: int) -> None:
    if position >= len(path):
        return

    idx = path[position]

    if isinstance(current, UnionNode):
        for opt in current.options:
            _validate_address_from(label, path, opt, position)
        return

    if not isinstance(current, TupleNode):
        raise ValueError(
            f"Address path {path!r} for label {label!r} descends into a "
            f"non-tuple at position {position}: shape is {current!r}."
        )
    if idx >= len(current.items) or idx < 0:
        raise ValueError(
            f"Address index {idx} is out of range for tuple of length "
            f"{len(current.items)} (label {label!r}, path {path!r})."
        )
    _validate_address_from(label, path, current.items[idx], position + 1)
