"""Public API for the new core: ``generate``.

Public entry point:
    generate(tree: Type[T], constraint: Expression = BooleanExpression(True), methods: Optional[Mapping[Label, Method]] = None) -> Set[T]
"""

from __future__ import annotations

from typing import Mapping, Optional, Type, TypeVar, cast

from equivalib.core.extension import Extension
from equivalib.core.expression import (
    BooleanExpression,
    Expression,
    And,
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
    Or,
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
    ExtensionNode,
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
_EXPR_TYPES = (
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
    if isinstance(node, ExtensionNode):
        raise ValueError("ExtensionNode should be resolved before concretize is called.")
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

    # 2. Extension initialize hooks and effective constraint
    constraint_eff = _effective_constraint(node, tree, constraint)

    # 3. Resolve extension leaves according to methods/addresses.
    node = _resolve_extensions(node, tree, constraint_eff, methods)

    # 4. Validate expression against the (still-unfilled) tree so that
    #    malformed or non-boolean constraints raise TypeError/ValueError
    #    before bounds inference has a chance to emit a misleading error.
    validate_expression(constraint_eff, node)

    # 5. Validate methods against the unfilled tree so that invalid method
    #    keys/values are always reported, even when bounds are contradictory
    #    and generate() would otherwise return early with an empty set.
    validate_methods(node, methods)

    # 6. Infer and fill integer bounds from the constraint
    bounds = infer_int_bounds(node, constraint_eff)
    if bounds:
        # Contradictory bounds (lo > hi) -> no solutions possible
        for _label, (lo, hi) in bounds.items():
            if lo > hi:
                return set()
        node = fill_int_bounds(node, bounds)

    # 7. Validate tree (requires bounds to have been filled)
    validate_tree(node)

    # 8. Fast path: no named nodes
    if not contains_name(node):
        satisfied = eval_expression(constraint_eff, {})
        if satisfied is not True:
            return set()
        return cast("set[GenerateT]", set(_values_node(node)))

    # 9. Exact satisfying-assignment search (S0)
    assignments = search(node, constraint_eff, methods)

    if not assignments:
        return set()

    # 10. Apply super-method reductions (S*)
    reduced = apply_methods(assignments, methods, labels_in_order(node))

    if not reduced:
        return set()

    # 11. Concretize each assignment into runtime values.
    result: set[object] = set()
    for asgn in reduced:
        result.update(concretize(node, asgn))

    return result  # type: ignore[return-value]


def _effective_constraint(node: IRNode, tree: Type[GenerateT], constraint: Expression) -> Expression:
    extras: list[Expression] = []
    for cls in _extension_classes(node):
        initialize = getattr(cls, "initialize", None)
        if not callable(initialize):
            raise ValueError(f"Extension class {cls!r} is missing callable initialize(...).")
        extra = initialize(tree, constraint)
        if extra is None:
            continue
        if not isinstance(extra, _EXPR_TYPES):
            raise TypeError("initialize(...) must return an Expression or None.")
        extras.append(extra)

    eff = constraint
    for extra in extras:
        eff = And(eff, extra)
    return eff


def _extension_classes(node: IRNode) -> set[type[Extension]]:
    classes: set[type[Extension]] = set()

    def walk(n: IRNode) -> None:
        if isinstance(n, ExtensionNode):
            classes.add(cast(type[Extension], n.owner))
            return
        if isinstance(n, TupleNode):
            for item in n.items:
                walk(item)
        elif isinstance(n, UnionNode):
            for opt in n.options:
                walk(opt)
        elif isinstance(n, NamedNode):
            walk(n.inner)

    walk(node)
    return classes


def _resolve_extensions(
    node: IRNode,
    tree: Type[GenerateT],
    constraint: Expression,
    methods: Mapping[Label, Method],
    address: str | None = None,
    current_label: str | None = None,
) -> IRNode:
    if isinstance(node, ExtensionNode):
        hook = methods.get(current_label, "all") if current_label is not None else "all"
        cls = cast(type[Extension], node.owner)
        values: list[Extension]
        if hook == "all":
            values = list(cls.enumerate_all(tree, constraint, address))
        elif hook == "arbitrary":
            one = cls.arbitrary(tree, constraint, address)
            values = [] if one is None else [one]
        else:
            one = cls.uniform_random(tree, constraint, address)
            values = [] if one is None else [one]
        for value in values:
            if not isinstance(value, cls):
                raise TypeError(
                    f"Extension hook for {cls.__qualname__} returned non-{cls.__qualname__} value: {value!r}."
                )
        literals = tuple(LiteralNode(v) for v in values)
        if not literals:
            return UnionNode(())
        if len(literals) == 1:
            return literals[0]
        return UnionNode(literals)
    if isinstance(node, TupleNode):
        items: list[IRNode] = []
        for idx, item in enumerate(node.items):
            child_address = f"{address}[{idx}]" if address is not None else f"[{idx}]"
            items.append(_resolve_extensions(item, tree, constraint, methods, child_address, current_label))
        return TupleNode(tuple(items))
    if isinstance(node, UnionNode):
        return UnionNode(tuple(_resolve_extensions(opt, tree, constraint, methods, address, current_label) for opt in node.options))
    if isinstance(node, NamedNode):
        return NamedNode(node.label, _resolve_extensions(node.inner, tree, constraint, methods, node.label, node.label))
    return node
