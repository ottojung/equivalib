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
    UnboundedIntNode,
    IntRangeNode,
    TupleNode,
    UnionNode,
    NamedNode,
    IRNode,
    contains_name,
    labels_in_order,
)
from equivalib.core.bounds_inference import infer_int_bounds, fill_int_bounds
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
    """Return the set of all runtime values that ``node`` can produce under ``assignment``."""
    if isinstance(node, NamedNode):
        return frozenset({assignment[node.label]})
    if isinstance(node, NoneNode):
        return frozenset({None})
    if isinstance(node, LiteralNode):
        return frozenset({node.value})
    if isinstance(node, BoolNode):
        return frozenset({True, False})
    if isinstance(node, UnboundedIntNode):
        raise ValueError("UnboundedIntNode should have been filled before concretize is called.")
    if isinstance(node, IntRangeNode):
        return frozenset(range(node.min_value, node.max_value + 1))
    if isinstance(node, TupleNode):
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
    """Generate all runtime values of type ``tree`` satisfying ``constraint``."""
    if methods is None:
        methods = {}

    # 1. Normalize
    node = normalize(tree)

    # 2. Validate expression against the (still-unfilled) tree so that
    #    malformed or non-boolean constraints raise TypeError/ValueError
    #    before bounds inference has a chance to emit a misleading error.
    validate_expression(constraint, node)

    # 3. Validate methods against the unfilled tree so that invalid method
    #    keys/values are always reported, even when bounds are contradictory
    #    and generate() would otherwise return early with an empty set.
    validate_methods(node, methods)

    # 4. Infer and fill integer bounds from the constraint
    bounds = infer_int_bounds(node, constraint)
    if bounds:
        # Contradictory bounds (lo > hi) -> no solutions possible
        for _label, (lo, hi) in bounds.items():
            if lo > hi:
                return set()
        node = fill_int_bounds(node, bounds)

    # 5. Validate tree (requires bounds to have been filled)
    validate_tree(node)

    # 6. Fast path: no named nodes
    if not contains_name(node):
        satisfied = eval_expression(constraint, {})
        if satisfied is not True:
            return set()
        return cast("set[GenerateT]", set(_values_node(node)))

    # 7. Exact satisfying-assignment search (S0)
    assignments = search(node, constraint, methods)

    if not assignments:
        return set()

    # 8. Apply super-method reductions (S*)
    reduced = apply_methods(assignments, methods, labels_in_order(node))

    if not reduced:
        return set()

    # 9. Concretize each assignment into runtime values.
    result: set[object] = set()
    for asgn in reduced:
        result.update(concretize(node, asgn))

    return result  # type: ignore[return-value]
