"""Public API for the new core: ``generate``.

Public entry point:
    generate(tree: Type[T], constraint: Expression = BooleanExpression(True), methods: Optional[Mapping[Label, Method]] = None, *, extensions: Optional[Mapping[type, object]] = None) -> Set[T]
"""

from __future__ import annotations

from typing import Mapping, Optional, Type, TypeVar, cast

from equivalib.core.expression import (
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
    ExtensionNode,
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

_REQUIRED_EXTENSION_METHODS = ("initialize", "enumerate_all", "arbitrary", "uniform_random")

_EXPR_TYPES = (
    BooleanConstant, IntegerConstant, Reference,
    Neg, Add, Sub, Mul, FloorDiv, Mod,
    Eq, Ne, Lt, Le, Gt, Ge, And, Or,
)


# ---------------------------------------------------------------------------
# Extension validation helpers
# ---------------------------------------------------------------------------

def _validate_extensions(extensions: object) -> dict[type, object]:
    """Validate the extensions argument and return it as a plain dict.

    Raises TypeError or ValueError for malformed extension registries.
    """
    if extensions is None:
        return {}
    if not isinstance(extensions, Mapping):
        raise TypeError(
            f"'extensions' must be a Mapping[type, object] or None, "
            f"got {type(extensions).__name__!r}. "
            "Pass a dict mapping leaf types to extension objects."
        )
    result: dict[type, object] = {}
    for key, ext_obj in extensions.items():
        if not isinstance(key, type):
            raise TypeError(
                f"extension key must be a type, got {type(key).__name__!r}: {key!r}. "
                "Use the class itself (e.g. Palette, not Palette('warm')) as the key."
            )
        for method_name in _REQUIRED_EXTENSION_METHODS:
            if not hasattr(ext_obj, method_name) or not callable(getattr(ext_obj, method_name)):
                raise TypeError(
                    f"Extension object for key {key!r} must have a callable "
                    f"'{method_name}' method. "
                    f"Got {type(ext_obj).__name__!r} which is missing '{method_name}'."
                )
        result[key] = ext_obj
    return result


def _collect_extension_label_nodes(node: IRNode) -> dict[str, ExtensionNode]:
    """Return {label: first ExtensionNode} for all named extension-owned labels."""
    result: dict[str, ExtensionNode] = {}

    def walk(n: IRNode) -> None:
        if isinstance(n, (NoneNode, BoolNode, LiteralNode, IntRangeNode, UnboundedIntNode, ExtensionNode)):
            return
        if isinstance(n, TupleNode):
            for item in n.items:
                walk(item)
        elif isinstance(n, UnionNode):
            for opt in n.options:
                walk(opt)
        elif isinstance(n, NamedNode):
            if isinstance(n.inner, ExtensionNode) and n.label not in result:
                result[n.label] = n.inner
            walk(n.inner)
        else:
            impossible(n)

    walk(node)
    return result


# ---------------------------------------------------------------------------
# Concretize
# ---------------------------------------------------------------------------

def concretize(node: IRNode, assignment: Mapping[str, object], extensions: dict[type, object] | None = None) -> frozenset[object]:
    """Return the set of all runtime values that ``node`` can produce under ``assignment``."""
    ext = extensions or {}
    if isinstance(node, NamedNode):
        return frozenset({assignment[node.label]})
    if isinstance(node, NoneNode):
        return frozenset({None})
    if isinstance(node, LiteralNode):
        return frozenset({node.value})
    if isinstance(node, BoolNode):
        return frozenset({True, False})
    if isinstance(node, ExtensionNode):
        # Unnamed extension leaf: enumerate its values directly.
        ext_obj = ext.get(node.key)
        if ext_obj is None:
            raise ValueError(
                f"No extension registered for key {node.key!r} during concretize."
            )
        return frozenset(ext_obj.enumerate_all(node.owner))  # type: ignore[union-attr]
    if isinstance(node, UnboundedIntNode):
        raise ValueError("UnboundedIntNode should have been filled before concretize is called.")
    if isinstance(node, IntRangeNode):
        return frozenset(range(node.min_value, node.max_value + 1))
    if isinstance(node, TupleNode):
        result: frozenset[object] = frozenset({()})
        for item in node.items:
            item_vals = concretize(item, assignment, ext)
            result = frozenset(
                existing + (v,) for existing in result for v in item_vals  # type: ignore[operator]
            )
        return result
    if isinstance(node, UnionNode):
        result = frozenset()
        for opt in node.options:
            result = result | concretize(opt, assignment, ext)
        return result
    impossible(node)


# ---------------------------------------------------------------------------
# Generate
# ---------------------------------------------------------------------------

def generate(
    tree: Type[GenerateT],
    constraint: Expression = _DEFAULT_CONSTRAINT,
    methods: Optional[Mapping[Label, Method]] = None,
    *,
    extensions: Optional[Mapping[type, object]] = None,
) -> set[GenerateT]:
    """Generate all runtime values of type ``tree`` satisfying ``constraint``."""
    if methods is None:
        methods = {}

    # 1. Validate and normalise the extensions registry.
    ext_dict = _validate_extensions(extensions)

    # 2. Call initialize() on every registered extension (in registration order).
    #    Each may return an additional boolean Expression to AND with the constraint.
    effective_constraint: Expression = constraint
    for ext_obj in ext_dict.values():
        extra = ext_obj.initialize(tree, constraint)  # type: ignore[union-attr]
        if extra is not None:
            # Validate: must be an Expression AST node.
            if not isinstance(extra, _EXPR_TYPES):
                raise TypeError(
                    f"Extension initialize() must return an Expression AST node or None, "
                    f"got {type(extra).__name__!r}: {extra!r}."
                )
            effective_constraint = And(effective_constraint, extra)

    # 3. Normalize (with extensions so custom leaves become ExtensionNode).
    node = normalize(tree, ext_dict)

    # 4. Validate the effective constraint against the normalized tree.
    validate_expression(effective_constraint, node)

    # 5. Validate methods against the tree.
    validate_methods(node, methods)

    # 6. Infer and fill integer bounds from the effective constraint.
    bounds = infer_int_bounds(node, effective_constraint)
    if bounds:
        for _label, (lo, hi) in bounds.items():
            if lo > hi:
                return set()
        node = fill_int_bounds(node, bounds)

    # 7. Validate tree (requires bounds to have been filled).
    validate_tree(node)

    # 8. Fast path: no named nodes.
    if not contains_name(node):
        satisfied = eval_expression(effective_constraint, {})
        if satisfied is not True:
            return set()
        return cast("set[GenerateT]", set(_values_node(node, ext_dict)))

    # 9. Build extension hooks: {label: (ext_obj, owner)} for extension-owned labels.
    ext_label_nodes = _collect_extension_label_nodes(node)
    extension_hooks: dict[str, tuple[object, object]] = {
        label: (ext_dict[ext_node.key], ext_node.owner)
        for label, ext_node in ext_label_nodes.items()
        if ext_node.key in ext_dict
    }

    # 10. Exact satisfying-assignment search (S0), handling arbitrary-infinite labels.
    assignments, arbitrary_infinite = search(node, effective_constraint, methods, ext_dict)

    if not assignments and not arbitrary_infinite:
        return set()
    if not assignments:
        # Only arbitrary-infinite labels: single empty assignment base.
        assignments = [{}]

    # 11. Apply super-method reductions (S*).
    reduced = apply_methods(assignments, methods, labels_in_order(node), extension_hooks)

    if not reduced:
        return set()

    # 12. Add arbitrary-infinite label values to each surviving assignment.
    for label, (ext_obj, owner) in arbitrary_infinite.items():
        arb_value = ext_obj.arbitrary(owner, None)  # type: ignore[union-attr]
        for asgn in reduced:
            asgn[label] = arb_value

    # 13. Concretize each assignment into runtime values.
    result: set[object] = set()
    for asgn in reduced:
        result.update(concretize(node, asgn, ext_dict))

    return result  # type: ignore[return-value]
