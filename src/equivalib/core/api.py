"""Public API for the new core: ``generate``.

Public entry point:
    generate(tree: Type[T], constraint: Expression = BooleanExpression(True), methods: Optional[Mapping[Label, Method]] = None) -> Set[T]
"""

from __future__ import annotations

from typing import Mapping, Optional, Type, TypeVar, cast

from equivalib.core.expression import (
    BooleanExpression,
    Expression,
    impossible,
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
    IRNode,
    contains_name,
    labels_in_order,
)
from equivalib.core.domains import _values_node
from equivalib.core.eval import eval_expression
from equivalib.core.search import search
from equivalib.core.methods import apply_methods, Label, Method

GenerateT = TypeVar("GenerateT")

_DEFAULT_CONSTRAINT: Expression = BooleanExpression(True)


# ---------------------------------------------------------------------------
# Concretize
# ---------------------------------------------------------------------------

def concretize(node: IRNode, assignment: Mapping[str, object]) -> frozenset[object]:
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
        result: frozenset[object] = frozenset({()})
        for item in node.items:
            item_vals = concretize(item, assignment)
            result = frozenset(
                existing + (v,) for existing in result for v in item_vals  # type: ignore[operator]
            )
        return result
    if isinstance(node, UnionNode):
        result = frozenset()
        for opt in node.options:
            result = result | concretize(opt, assignment)
        return result
    impossible(node)


# ---------------------------------------------------------------------------
# Generate
# ---------------------------------------------------------------------------

def generate(
    tree: Type[GenerateT],
    constraint: Expression = _DEFAULT_CONSTRAINT,
    methods: Optional[Mapping[Label, Method]] = None,
) -> set[GenerateT]:
    """Generate all runtime values of type ``tree`` satisfying ``constraint``.

    Args:
        tree:       A Python type expression (TypeTree).
        constraint: An Expression AST.  Defaults to BooleanExpression(True).
        methods:    Optional mapping from label string to method string.
                    Absent labels default to ``"all"``.  ``None`` is treated
                    the same as an empty mapping.

    Returns:
        A set of runtime values.

    Raises:
        ValueError: on invalid tree, methods, or expression.
        TypeError:  if ``constraint`` is not an Expression AST node.
    """
    if methods is None:
        methods = {}

    # 1. Normalize
    node = normalize(tree)

    # 2. Validate tree
    validate_tree(node)

    # 3. Validate methods
    validate_methods(node, methods)

    # 4. Validate expression
    validate_expression(constraint, node)

    # 5. Fast path: no named nodes → evaluate the (constant) constraint first,
    #    then return the full denotation if satisfied.
    if not contains_name(node):
        # For unnamed trees there are no labels, so the constraint must be
        # a constant boolean expression.  Evaluate it with an empty assignment.
        satisfied = eval_expression(constraint, {})
        if satisfied is not True:
            return set()
        return cast("set[GenerateT]", set(_values_node(node)))

    # 6. Exact satisfying-assignment search (S0)
    assignments = search(node, constraint)

    if not assignments:
        return set()

    # 7. Apply super-method reductions (S*)
    reduced = apply_methods(assignments, methods, labels_in_order(node))

    if not reduced:
        return set()

    # 8. Concretize each assignment into runtime values.
    # ``concretize`` returns a frozenset (possibly multi-valued for unnamed
    # leaves in mixed trees), so we union the results together.
    result: set[object] = set()
    for asgn in reduced:
        result.update(concretize(node, asgn))

    return result  # type: ignore[return-value]
