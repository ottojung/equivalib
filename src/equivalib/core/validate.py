"""Static validators for trees, methods, and expressions.

Three public entry points:
    validate_tree(node)
    validate_methods(node, methods)
    validate_expression(expr, node)
"""

from __future__ import annotations

from typing import Any, Mapping

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

# Expression type categories used for type-checking operands
_NUMERIC_NODES = (IntegerConstant, Reference, Neg, Add, Sub, Mul, FloorDiv, Mod)
_BOOL_NODES = (BooleanConstant, Eq, Ne, Lt, Le, Gt, Ge, And, Or)
_ANY_EXPR_NODES = _NUMERIC_NODES + _BOOL_NODES


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
    result_type = _check_expr_type(expr, known_labels, label_shapes, require_bool=False)
    if result_type == "numeric":
        raise TypeError(
            f"Top-level constraint must be a boolean expression, got a numeric "
            f"expression: {expr!r}."
        )


def _collect_label_shapes(node: object) -> dict:
    """Return a mapping {label: shape_node} for all named nodes in the tree."""
    result: dict = {}
    _walk_for_shapes(node, result)
    return result


def _walk_for_shapes(node: object, result: dict) -> None:
    if isinstance(node, (NoneNode, BoolNode, LiteralNode, IntRangeNode)):
        return
    if isinstance(node, TupleNode):
        for item in node.items:
            _walk_for_shapes(item, result)
    elif isinstance(node, UnionNode):
        for opt in node.options:
            _walk_for_shapes(opt, result)
    elif isinstance(node, NamedNode):
        result[node.label] = tree_shape(node.inner)
        _walk_for_shapes(node.inner, result)


def _check_expr_type(expr: object, known_labels: frozenset, label_shapes: dict, require_bool: bool) -> str:
    """Return 'bool' or 'numeric' (or raise if invalid)."""
    if isinstance(expr, BooleanConstant):
        if require_bool is False:
            pass  # BooleanConstant can appear in any position for now
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
        elif expr.path:
            raise ValueError(
                f"Label {expr.label!r} is not in label_shapes but has a non-empty path."
            )
        # References to named nodes whose shape is a tuple can yield numeric or
        # other values depending on the path – we treat all reference results as
        # opaque (allow either position) for simplicity.
        return "any"

    if isinstance(expr, Neg):
        t = _check_expr_type(expr.operand, known_labels, label_shapes, require_bool=False)
        if t == "bool":
            raise TypeError(f"Neg operand must not be boolean: {expr!r}")
        return "numeric"

    if isinstance(expr, (Add, Sub, Mul, FloorDiv, Mod)):
        lt = _check_expr_type(expr.left, known_labels, label_shapes, require_bool=False)
        rt = _check_expr_type(expr.right, known_labels, label_shapes, require_bool=False)
        if lt == "bool" or rt == "bool":
            raise TypeError(f"Arithmetic operands must not be boolean: {expr!r}")
        return "numeric"

    if isinstance(expr, (Eq, Ne)):
        _check_expr_type(expr.left, known_labels, label_shapes, require_bool=False)
        _check_expr_type(expr.right, known_labels, label_shapes, require_bool=False)
        return "bool"

    if isinstance(expr, (Lt, Le, Gt, Ge)):
        lt = _check_expr_type(expr.left, known_labels, label_shapes, require_bool=False)
        rt = _check_expr_type(expr.right, known_labels, label_shapes, require_bool=False)
        if lt == "bool" or rt == "bool":
            raise TypeError(f"Ordering operands must not be boolean: {expr!r}")
        return "bool"

    if isinstance(expr, (And, Or)):
        lt = _check_expr_type(expr.left, known_labels, label_shapes, require_bool=True)
        rt = _check_expr_type(expr.right, known_labels, label_shapes, require_bool=True)
        if lt != "bool" and lt != "any":
            raise TypeError(f"{type(expr).__name__} left operand must be boolean: {expr!r}")
        if rt != "bool" and rt != "any":
            raise TypeError(f"{type(expr).__name__} right operand must be boolean: {expr!r}")
        return "bool"

    # Anything that is not an Expression node is a type error.
    raise TypeError(
        f"Expression must be an AST node, got {type(expr).__name__!r}: {expr!r}"
    )


def _validate_address(label: str, path: tuple, shape: object) -> None:
    """Raise ValueError if ``path`` is not a valid address into ``shape``."""
    current = shape
    for i, idx in enumerate(path):
        if not isinstance(current, TupleNode):
            raise ValueError(
                f"Address path {path!r} for label {label!r} descends into a "
                f"non-tuple at position {i}: shape is {current!r}."
            )
        # A Union where some branches are tuples and others are not is ambiguous.
        # We need every possible shape along the path to be a tuple.
        if isinstance(current, UnionNode):
            for opt in current.options:
                if not isinstance(opt, TupleNode):
                    raise ValueError(
                        f"Address path {path!r} for label {label!r} crosses a "
                        f"union that contains a non-tuple option: {opt!r}."
                    )
            # All options are tuples; take the first one for length check.
            current = current.options[0]
        if not isinstance(current, TupleNode):
            raise ValueError(
                f"Address path {path!r} for label {label!r} descends into "
                f"non-tuple at position {i}: shape is {current!r}."
            )
        if idx >= len(current.items) or idx < 0:
            raise ValueError(
                f"Address index {idx} is out of range for tuple of length "
                f"{len(current.items)} (label {label!r}, path {path!r})."
            )
        current = current.items[idx]

    # If the shape at a union contains non-tuple options we should already have
    # caught that above. No further checks needed for zero-length paths.


