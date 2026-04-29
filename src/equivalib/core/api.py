"""Public API for the new core: ``generate``.

Public entry point:
    generate(tree: Type[T], constraint: Expression = BooleanExpression(True), methods: Optional[Mapping[Label, Method]] = None) -> Set[T]
"""

from __future__ import annotations

import random
from typing import Mapping, Optional, Type, TypeVar, cast

from equivalib.core.extension import Extension
from equivalib.core.expression import (
    BooleanExpression,
    Expression,
    ParsedExpression,
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
    reference,
)
from equivalib.core.parser import parse
from equivalib.core.normalize import normalize
from equivalib.core.validate import validate_tree, validate_methods, validate_expression, _is_index_label
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
from equivalib.core.order import canonical_first
from equivalib.core.search import search
from equivalib.core.methods import apply_methods, Label, Method, tag_value, structural_eq

GenerateT = TypeVar("GenerateT")

_DEFAULT_CONSTRAINT: ParsedExpression = BooleanExpression(True)
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
_OTHER_EXPORTS = (reference,)


# ---------------------------------------------------------------------------
# Unnamed-tree method helpers
# ---------------------------------------------------------------------------

def _normalize_self_in_methods(methods: Mapping[Label, Method]) -> Mapping[Label, Method]:
    """Normalize the ``"self"`` method key to ``""`` (the root label synonym).

    ``"self"`` and ``""`` are synonyms for the root method key on unnamed
    trees.  If both appear in the same mapping, a ``ValueError`` is raised
    because the intent is ambiguous.
    """
    if "self" not in methods:
        return methods
    if "" in methods:
        raise ValueError(
            "Cannot specify both 'self' and '' in methods; they are synonyms "
            "for the root label.  Use one or the other, not both."
        )
    return {("" if k == "self" else k): v for k, v in methods.items()}


def _parse_index_methods(methods: Mapping[Label, Method]) -> dict[int, str]:
    """Parse ``'[i]'``-style method keys into ``{position: method}`` pairs."""
    result: dict[int, str] = {}
    for key, method in methods.items():
        if isinstance(key, str) and _is_index_label(key):
            result[int(key[1:-1])] = method
    return result


def _needs_unnamed_filtering(methods: Mapping[Label, Method]) -> bool:
    """Return True if ``methods`` contains any non-``"all"`` unnamed-tree key.

    When this returns False the entire satisfying set can be streamed directly
    to a ``set`` without materializing an intermediate list.
    """
    if not isinstance(methods, Mapping):
        return False
    root_method = methods.get("")
    if root_method is not None and root_method != "all":
        return True
    for key, method in methods.items():
        if isinstance(key, str) and _is_index_label(key) and method != "all":
            return True
    return False

def _pick_witness(values: list[object], method: str) -> object:
    """Return a single representative value from ``values`` according to ``method``.

    Args:
        values:  Non-empty list of satisfying values to choose from.
        method:  One of ``"arbitrary"`` (canonical-minimum) or
                 ``"uniform_random"`` (random element with replacement).

    Raises:
        ValueError: if ``method`` is not a recognised method string.
    """
    distinct: list[object] = []
    seen: set[object] = set()
    for v in values:
        tag = tag_value(v)
        if tag not in seen:
            seen.add(tag)
            distinct.append(v)
    if method == "arbitrary":
        return canonical_first(distinct)
    if method == "uniform_random":
        return random.choices(values, k=1)[0]
    raise ValueError(f"Unknown method {method!r}.")


def _apply_unnamed_methods(
    values: list[object],
    methods: Mapping[Label, Method],
    node: IRNode,
) -> list[object]:
    """Apply root (``""``) or positional (``"[i]"``) methods to satisfying values.

    Used for trees that have no ``Name(...)`` labels.  Constraints use the
    standard anonymous integer-index references — ``reference(i)`` producing
    ``Reference(None, (i,))`` — for tuple elements; no tree modification or
    constraint rewriting is needed.

    * Index methods ``"[i]"``: applied element-by-element, left-to-right, to
      the list of satisfying tuples.  Elements without an explicit method
      default to ``"all"`` (no filtering).
    * Root method ``""``: applied to the whole list of satisfying values as
      a single unit.
    * Empty or irrelevant methods: values are returned unchanged.
    """
    if not values or not isinstance(methods, Mapping):
        return values

    index_methods = _parse_index_methods(methods)

    if index_methods and isinstance(node, TupleNode):
        return _apply_positional_methods(values, len(node.items), index_methods)

    root_method = methods.get("")
    if root_method is None or root_method == "all":
        return values

    witness = _pick_witness(values, root_method)
    return [v for v in values if structural_eq(v, witness)]


def _apply_positional_methods(
    values: list[object],
    n_elements: int,
    index_methods: dict[int, str],
) -> list[object]:
    """Filter tuples by per-element methods, processing elements left-to-right."""
    current = values
    for i in range(n_elements):
        method = index_methods.get(i, "all")
        if method == "all":
            continue
        projection = [cast(tuple[object, ...], t)[i] for t in current]
        if not projection:
            return []
        witness = _pick_witness(projection, method)
        current = [t for t in current if structural_eq(cast(tuple[object, ...], t)[i], witness)]
        if not current:
            return []
    return current


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
    """Generate all runtime values of type ``tree`` satisfying ``constraint``.

    ``constraint`` may be a string expression (``RawExpression``) or an
    already-constructed ``ParsedExpression`` AST node.  String expressions are
    parsed with :func:`equivalib.core.parser.parse` before processing.
    """
    if methods is None:
        methods = {}

    # 0a. Normalize the 'self' method key to '' (they are synonyms).
    methods = _normalize_self_in_methods(methods)

    # 0. Parse string constraint into a ParsedExpression.
    if isinstance(constraint, str):
        parsed_constraint: ParsedExpression = parse(constraint)
    elif isinstance(constraint, _EXPR_TYPES):
        parsed_constraint = constraint
    else:
        impossible(constraint)

    # 1. Normalize
    node = normalize(tree)

    # 2. Extension initialize hooks and effective constraint
    constraint_eff = _effective_constraint(node, tree, parsed_constraint)

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

    # 8. Unnamed-tree path (no named nodes): enumerate satisfying values.
    #    When no index/root filtering is needed we stream directly into a set
    #    to avoid a redundant list allocation; otherwise we materialize a list
    #    so that _apply_unnamed_methods can select a positional witness.
    if not contains_name(node):
        satisfying_iter = (
            value for value in _values_node(node)
            if eval_expression(constraint_eff, {None: value}) is True
        )
        if not _needs_unnamed_filtering(methods):
            return cast(set[GenerateT], set(satisfying_iter))
        satisfying = list(satisfying_iter)
        return cast(set[GenerateT], set(_apply_unnamed_methods(satisfying, methods, node)))

    # 9. Exact satisfying-assignment search (S0)
    assignments = search(node, constraint_eff, methods)

    if not assignments:
        return set()

    # 10. Apply super-method reductions (S*)
    reduced = apply_methods(assignments, methods, labels_in_order(node))

    if not reduced:
        return set()

    # 11. Concretize each assignment into runtime values.
    concrete_results: set[object] = set()
    for asgn in reduced:
        concrete_results.update(concretize(node, asgn))

    return concrete_results  # type: ignore[return-value]


def _effective_constraint(node: IRNode, tree: Type[GenerateT], constraint: ParsedExpression) -> ParsedExpression:
    extras: list[ParsedExpression] = []
    for cls in _extension_classes(node):
        initialize = getattr(cls, "initialize", None)
        if not callable(initialize):
            raise ValueError(f"Extension class {cls!r} is missing callable initialize(...).")
        extra = initialize(tree, constraint)
        if extra is None:
            continue
        if not isinstance(extra, _EXPR_TYPES):
            raise TypeError("initialize(...) must return a ParsedExpression or None.")
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
    constraint: ParsedExpression,
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
