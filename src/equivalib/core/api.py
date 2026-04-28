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
    labels as _tree_labels,
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
# Virtual-label translation helpers
# ---------------------------------------------------------------------------

def _is_index_label(label: str) -> bool:
    """Return True if ``label`` is an index-style label like '[0]', '[42]', etc."""
    if not (label.startswith("[") and label.endswith("]")):
        return False
    return label[1:-1].isdigit()


def _rewrite_refs(
    expr: Expression,
    index_mode: bool,
    has_root: bool,
) -> Expression:
    """Recursively rewrite ``Reference(None, path)`` to use virtual label names.

    When ``has_root`` is True, ``Reference(None, path)`` becomes
    ``Reference("", path)`` (root label).

    When ``index_mode`` is True, every ``Reference(None, (i, *rest))`` becomes
    ``Reference(f"[{i}]", rest)``.  This includes out-of-range indices so that
    normal label validation can report the real error ("unknown label '[5]'")
    rather than the misleading "root/index-only references are not supported
    when the tree has named labels" message.
    """
    if isinstance(expr, (BooleanConstant, IntegerConstant)):
        return expr
    if isinstance(expr, Reference):
        if expr.label is None:
            path = tuple(expr.path)
            if index_mode and path and isinstance(path[0], int):
                return Reference(f"[{path[0]}]", path[1:])
            if has_root:
                return Reference("", path)
        return expr
    if isinstance(expr, Neg):
        new_op = _rewrite_refs(expr.operand, index_mode, has_root)
        return Neg(new_op) if new_op is not expr.operand else expr
    if isinstance(expr, (Add, Sub, Mul, FloorDiv, Mod, Eq, Ne, Lt, Le, Gt, Ge, And, Or)):
        new_l = _rewrite_refs(expr.left, index_mode, has_root)
        new_r = _rewrite_refs(expr.right, index_mode, has_root)
        if new_l is expr.left and new_r is expr.right:
            return expr
        return type(expr)(new_l, new_r)
    return expr


def _translate_virtual_labels(
    node: IRNode,
    constraint: Expression,
    methods: Mapping[Label, Method],
) -> tuple[IRNode, Expression]:
    """Insert virtual NamedNodes and rewrite the constraint for index/root method labels.

    When ``methods`` contains the root label ``""`` or index-style labels
    ``"[0]"``, ``"[1]"``, etc., and the tree has no existing named labels,
    this function:

    1. Wraps the corresponding unnamed subtrees in ``NamedNode`` wrappers so
       that the standard named-label machinery (SAT encoding, ``apply_methods``,
       ``concretize``) can process them.
    2. Rewrites every ``Reference(None, ...)`` in the constraint so that its
       label matches the newly added ``NamedNode`` label.

    Index labels take priority: if any ``"[i]"`` keys are present and the root
    is a ``TupleNode``, per-element ``NamedNode`` wrappers are added for each
    referenced index and root-index references of the form
    ``Reference(None, (i, *rest))`` are rewritten to ``Reference("[i]", rest)``.

    If only ``""`` is present (no index labels, or the root is not a
    ``TupleNode``), the whole root is wrapped in ``NamedNode("")`` and every
    ``Reference(None, path)`` is rewritten to ``Reference("", path)``.

    The translation is skipped entirely when the tree already has explicit
    named labels (i.e. contains ``NamedNode`` wrappers from ``Name(...)``
    annotations), because named-label and virtual-label addressing must not
    be mixed on the same tree.
    """
    # Guard: if methods is not a Mapping or has non-str keys, let validate_methods
    # handle it with the correct error type/message.
    if not isinstance(methods, Mapping):
        return node, constraint
    str_keys = {lbl for lbl in methods if isinstance(lbl, str)}

    if not str_keys:
        return node, constraint

    # Don't interfere when the tree already carries explicit named labels.
    if _tree_labels(node):
        return node, constraint

    has_root = "" in str_keys
    index_labels = {lbl for lbl in str_keys if _is_index_label(lbl)}

    if not has_root and not index_labels:
        return node, constraint

    if index_labels and isinstance(node, TupleNode):
        # Reject the combination of root label and index labels on the same
        # unnamed tuple root with a targeted error message.
        if has_root:
            raise ValueError(
                "Cannot combine the root label \"\" with index-style labels "
                f"({sorted(index_labels)!r}) on the same unnamed tuple root. "
                "Use either \"\" (for the tuple as a whole) or \"[i]\" labels "
                "(for individual elements), but not both."
            )
        # Wrap ALL tuple elements with virtual NamedNodes so that root-index
        # References in the constraint can be rewritten uniformly, even when
        # only a subset of elements appear in methods (partial coverage).
        # Elements absent from methods default to method "all".
        items = list(node.items)
        for idx, item in enumerate(items):
            label = f"[{idx}]"
            if not isinstance(item, NamedNode):
                items[idx] = NamedNode(label, item)
        new_node: IRNode = TupleNode(tuple(items))
        new_constraint = _rewrite_refs(constraint, True, False)
        return new_node, new_constraint

    if has_root and not isinstance(node, NamedNode):
        # Wrap the whole root in a virtual NamedNode("").
        new_node = NamedNode("", node)
        new_constraint = _rewrite_refs(constraint, False, True)
        return new_node, new_constraint

    return node, constraint


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

    # 3.5. Insert virtual NamedNodes for index/root method labels and rewrite
    #      root-index References in the constraint so that the standard named-label
    #      machinery (bounds inference, SAT encoding, apply_methods, concretize)
    #      can process the formerly anonymous tree.
    node, constraint_eff = _translate_virtual_labels(node, constraint_eff, methods)

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
        result: set[GenerateT] = set()
        for value in _values_node(node):
            satisfied = eval_expression(constraint_eff, {None: value})
            if satisfied is True:
                result.add(cast(GenerateT, value))
        return result

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
