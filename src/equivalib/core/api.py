"""Public API for the new core: ``generate``.

Public entry point:
    generate(tree, constraint=BooleanExpression(True), methods=None) -> set
"""

from __future__ import annotations

from typing import Any, Mapping, Optional

from equivalib.core.expression import (
    BooleanExpression,
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

def concretize(node: object, assignment: Mapping[str, Any]) -> frozenset[Any]:
    """Return the set of all runtime values that ``node`` can produce under ``assignment``.

    Rules:
        - ``NamedNode(label, inner)`` collapses atomically to ``{assignment[label]}``.
        - Unnamed leaves (``BoolNode``, ``IntRangeNode``, ``LiteralNode``, ``NoneNode``)
          expand to their full denotation, just as ``_values_node`` would.
        - ``TupleNode`` produces the cartesian product of its children's expansions.
        - ``UnionNode`` produces the set union of its children's expansions.

    Returns a ``frozenset`` of hashable runtime values.
    """
    if isinstance(node, NamedNode):
        return frozenset({assignment[node.label]})
    if isinstance(node, NoneNode):
        return frozenset({None})
    if isinstance(node, LiteralNode):
        return frozenset({node.value})
    if isinstance(node, BoolNode):
        return frozenset({True, False})
    if isinstance(node, IntRangeNode):
        return frozenset(range(node.min_value, node.max_value + 1))
    if isinstance(node, TupleNode):
        # Cartesian product of all children's expansions.
        result: frozenset[Any] = frozenset({()})
        for item in node.items:
            item_vals = concretize(item, assignment)
            result = frozenset(
                existing + (v,) for existing in result for v in item_vals
            )
        return result
    if isinstance(node, UnionNode):
        result = frozenset()
        for opt in node.options:
            result = result | concretize(opt, assignment)
        return result
    raise TypeError(f"Unknown IR node: {type(node)}")


# ---------------------------------------------------------------------------
# Generate
# ---------------------------------------------------------------------------

def generate(
    tree: Any,
    constraint: Any = None,
    methods: Optional[Mapping[str, str]] = None,
) -> set[Any]:
    """Generate all runtime values of type ``tree`` satisfying ``constraint``.

    Args:
        tree:       A Python type expression (TypeTree).
        constraint: An Expression AST.  Defaults to BooleanExpression(True).
        methods:    Mapping from label string to method string.
                    Absent labels default to ``"all"``.

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

    # 7. Apply super-method reductions (S*)
    reduced = apply_methods(assignments, methods)

    if not reduced:
        return set()

    # 8. Concretize each assignment into runtime values.
    # ``concretize`` returns a frozenset (possibly multi-valued for unnamed
    # leaves in mixed trees), so we union the results together.
    result: set[Any] = set()
    for asgn in reduced:
        result.update(concretize(node, asgn))

    return result


def _is_expression(obj: Any) -> bool:
    """Return True iff ``obj`` is a known Expression AST node."""
    return isinstance(obj, (
        BooleanConstant, IntegerConstant, Reference,
        Neg, Add, Sub, Mul, FloorDiv, Mod,
        Eq, Ne, Lt, Le, Gt, Ge, And, Or,
    ))
