"""Public API for the new core: ``generate`` and ``concretize``.

Public entry point:
    generate(tree, constraint=BooleanExpression(True), methods=None) -> set
"""

from __future__ import annotations

from typing import Any, Mapping

from equivalib.core.expression import BooleanConstant, BooleanExpression
from equivalib.core.normalize import normalize
from equivalib.core.validate import validate_tree, validate_methods, validate_expression
from equivalib.core.types import (
    NoneNode,
    BoolNode,
    LiteralNode,
    IntRangeNode,
    TupleNode,
    UnionNode,
    NamedNode,
    contains_name,
)
from equivalib.core.domains import _values_node
from equivalib.core.search import search
from equivalib.core.methods import apply_methods


# ---------------------------------------------------------------------------
# Concretize
# ---------------------------------------------------------------------------

def concretize(node: object, assignment: dict) -> Any:
    """Turn an IR node into a runtime value given a label assignment.

    Rules:
        - unnamed nodes expand fully (using the assignment for inner names)
        - NamedNode(label, inner) collapses atomically to assignment[label]
    """
    if isinstance(node, NoneNode):
        return None
    if isinstance(node, BoolNode):
        # Unnamed bool should not appear in concretize for named trees;
        # this case handles trees without any names at all.
        raise TypeError("BoolNode must be reached through a NamedNode or _values_node path.")
    if isinstance(node, LiteralNode):
        return node.value
    if isinstance(node, IntRangeNode):
        raise TypeError("IntRangeNode must be reached through a NamedNode or _values_node path.")
    if isinstance(node, TupleNode):
        return tuple(concretize(item, assignment) for item in node.items)
    if isinstance(node, UnionNode):
        raise TypeError("UnionNode cannot be directly concretized without an assignment.")
    if isinstance(node, NamedNode):
        return assignment[node.label]
    raise TypeError(f"Unknown IR node: {type(node)}")


# ---------------------------------------------------------------------------
# Generate
# ---------------------------------------------------------------------------

def generate(
    tree: Any,
    constraint: Any = None,
    methods: Mapping[str, str] | None = None,
) -> set:
    """Generate all runtime values of type ``tree`` satisfying ``constraint``.

    Args:
        tree:       A Python type expression (TypeTree).
        constraint: An Expression AST.  Defaults to BooleanExpression(True).
        methods:    Mapping from label string to method string.

    Returns:
        A set of runtime values.

    Raises:
        ValueError: on invalid tree, methods, or expression.
        TypeError:  if ``constraint`` is not an Expression AST node.
    """
    if constraint is None:
        constraint = BooleanExpression(True)
    if methods is None:
        methods = {}

    # Reject non-AST constraints (e.g. strings)
    if not _is_expression(constraint):
        raise TypeError(
            f"Constraint must be an Expression AST node, got {type(constraint).__name__!r}."
        )

    # 1. Normalize
    node = normalize(tree)

    # 2. Validate tree
    validate_tree(node)

    # 3. Validate methods
    validate_methods(node, methods)

    # 4. Validate expression
    validate_expression(constraint, node)

    # 5. Fast path: no named nodes → just return the full denotation
    if not contains_name(node):
        return set(_values_node(node))

    # 6. Exact satisfying-assignment search (S0)
    assignments = search(node, constraint)

    if not assignments:
        return set()

    # 7. Apply super-method reductions (S* )
    reduced = apply_methods(assignments, methods)

    if not reduced:
        return set()

    # 8. Concretize each assignment into runtime values
    result = set()
    for asgn in reduced:
        result.add(_concretize_tree(node, asgn))

    return result


def _is_expression(obj: Any) -> bool:
    """Return True iff ``obj`` is a known Expression AST node."""
    from equivalib.core.expression import (
        BooleanConstant, IntegerConstant, Reference,
        Neg, Add, Sub, Mul, FloorDiv, Mod,
        Eq, Ne, Lt, Le, Gt, Ge, And, Or,
    )
    return isinstance(obj, (
        BooleanConstant, IntegerConstant, Reference,
        Neg, Add, Sub, Mul, FloorDiv, Mod,
        Eq, Ne, Lt, Le, Gt, Ge, And, Or,
    ))


def _concretize_tree(node: object, assignment: dict) -> Any:
    """Concretize a tree node given a complete label assignment.

    This function is aware of the tree structure and handles all node types
    without raising on BoolNode / IntRangeNode / UnionNode in the unnamed
    case (it uses _values_node for those).
    """
    if isinstance(node, NamedNode):
        return assignment[node.label]
    if isinstance(node, NoneNode):
        return None
    if isinstance(node, (BoolNode, LiteralNode, IntRangeNode)):
        # Unnamed leaf: if we got here, there is no assignment for this node
        # (it should be reached through a NamedNode).  This can only happen in
        # a mixed tree.  Raise clearly.
        raise TypeError(
            f"Unnamed leaf {node!r} reached during concretization; "
            "check that all free leaves are wrapped in NamedNode."
        )
    if isinstance(node, TupleNode):
        return tuple(_concretize_tree(item, assignment) for item in node.items)
    if isinstance(node, UnionNode):
        # Find the first option whose concretized form is reachable.
        raise TypeError("UnionNode reached during concretization without a NamedNode wrapper.")
    raise TypeError(f"Unknown IR node: {type(node)}")
