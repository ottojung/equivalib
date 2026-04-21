"""Public API for the new core: ``generate``.

Public entry point:
    generate(tree, constraint, methods, *, extensions) -> Set[T]
"""

from __future__ import annotations

from typing import Any, Mapping, Optional, Type, TypeVar, cast

from equivalib.core.expression import (
    And,
    BooleanExpression,
    Expression,
    impossible,
)
from equivalib.core.normalize import normalize, normalize_with_extensions
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
    ExtensionLeafNode,
    IRNode,
    contains_name,
    labels_in_order,
)
from equivalib.core.bounds_inference import infer_int_bounds, fill_int_bounds
from equivalib.core.domains import _values_node
from equivalib.core.eval import eval_expression
from equivalib.core.search import search
from equivalib.core.methods import apply_methods, Label, Method
from equivalib.core.extensions import validate_extensions, run_initialize

GenerateT = TypeVar("GenerateT")

_DEFAULT_CONSTRAINT: Expression = BooleanExpression(True)

# Sentinel for extension labels whose domain cannot be enumerated (infinite).
_INFINITE_SENTINEL: object = object()


# ---------------------------------------------------------------------------
# Concretize
# ---------------------------------------------------------------------------

def concretize(
    node: IRNode,
    assignment: Mapping[str, object],
    extensions: Mapping[type, Any] | None = None,
) -> frozenset[object]:
    """Return the set of all runtime values that ``node`` can produce under ``assignment``."""
    if isinstance(node, NamedNode):
        return frozenset({assignment[node.label]})
    if isinstance(node, NoneNode):
        return frozenset({None})
    if isinstance(node, LiteralNode):
        return frozenset({node.value})
    if isinstance(node, BoolNode):
        return frozenset({True, False})
    if isinstance(node, ExtensionLeafNode):
        if extensions is None:
            raise ValueError(f"ExtensionLeafNode encountered without extensions: {node.owner!r}.")
        ext = extensions[node.extension_type]
        return frozenset(ext.enumerate_all(node.owner))
    if isinstance(node, UnboundedIntNode):
        raise ValueError("UnboundedIntNode should have been filled before concretize is called.")
    if isinstance(node, IntRangeNode):
        return frozenset(range(node.min_value, node.max_value + 1))
    if isinstance(node, TupleNode):
        result: frozenset[object] = frozenset({()})
        for item in node.items:
            item_vals = concretize(item, assignment, extensions)
            result = frozenset(
                existing + (v,) for existing in result for v in item_vals  # type: ignore[operator]
            )
        return result
    if isinstance(node, UnionNode):
        result = frozenset()
        for opt in node.options:
            result = result | concretize(opt, assignment, extensions)
        return result
    impossible(node)


# ---------------------------------------------------------------------------
# Helper: collect extension label info (domain lists + enum errors)
# ---------------------------------------------------------------------------

def _collect_ext_label_info(
    node: IRNode,
    ext_label_first_domains: dict[str, list[object]],
    ext_label_occ_sets: dict[str, list[frozenset[object]]],
    ext_label_first: dict[str, tuple[object, type]],
    ext_label_enum_errors: dict[str, BaseException],
    extensions: Mapping[type, Any],
) -> None:
    """Walk *node* and collect per-occurrence domains for extension-owned named leaves.

    For each named extension leaf, calls ``enumerate_all`` and records:
    - The ordered domain list for the first occurrence (preserved for stable ordering).
    - A frozenset per occurrence (used for intersection across repeated labels).
    - Any exception raised by ``enumerate_all`` (e.g. for infinite domains).
    """
    if isinstance(node, (NoneNode, BoolNode, LiteralNode, IntRangeNode, UnboundedIntNode, ExtensionLeafNode)):
        return
    if isinstance(node, TupleNode):
        for item in node.items:
            _collect_ext_label_info(item, ext_label_first_domains, ext_label_occ_sets,
                                    ext_label_first, ext_label_enum_errors, extensions)
    elif isinstance(node, UnionNode):
        for opt in node.options:
            _collect_ext_label_info(opt, ext_label_first_domains, ext_label_occ_sets,
                                    ext_label_first, ext_label_enum_errors, extensions)
    elif isinstance(node, NamedNode):
        if isinstance(node.inner, ExtensionLeafNode):
            label = node.label
            owner = node.inner.owner
            ext_type = node.inner.extension_type
            extension = extensions[ext_type]

            if label in ext_label_enum_errors:
                # Already recorded as an error — no further action needed.
                return

            try:
                domain_list = list(extension.enumerate_all(owner))
            except Exception as exc:  # noqa: BLE001
                # Enumeration failed (e.g. infinite domain).
                if label not in ext_label_first:
                    ext_label_first[label] = (owner, ext_type)
                ext_label_enum_errors[label] = exc
                return

            domain_set = frozenset(domain_list)
            if label not in ext_label_occ_sets:
                ext_label_occ_sets[label] = []
                ext_label_first[label] = (owner, ext_type)
                ext_label_first_domains[label] = domain_list  # preserve order
            ext_label_occ_sets[label].append(domain_set)
        else:
            _collect_ext_label_info(node.inner, ext_label_first_domains, ext_label_occ_sets,
                                    ext_label_first, ext_label_enum_errors, extensions)
    else:
        impossible(node)


# ---------------------------------------------------------------------------
# Generate
# ---------------------------------------------------------------------------

def generate(
    tree: Type[GenerateT],
    constraint: Expression = _DEFAULT_CONSTRAINT,
    methods: Optional[Mapping[Label, Method]] = None,
    *,
    extensions: Optional[Mapping[type, Any]] = None,
) -> set[GenerateT]:
    """Generate all runtime values of type ``tree`` satisfying ``constraint``.

    Parameters
    ----------
    tree:
        A type annotation describing the space to generate from.
    constraint:
        A boolean expression over named labels (default: True).
    methods:
        Optional mapping of label → method string ("all", "arbitrary", "uniform_random").
    extensions:
        Optional mapping of type → Extension object.
    """
    # --- Validate and normalise extensions ---
    validate_extensions(extensions)
    if extensions is None:
        extensions = {}

    # --- Call initialize on all registered extensions ---
    extra_constraints = run_initialize(extensions, tree, constraint)
    effective_constraint: Expression = constraint
    for extra in extra_constraints:
        effective_constraint = And(effective_constraint, extra)

    if methods is None:
        methods = {}

    # --- Normalize ---
    if extensions:
        node = normalize_with_extensions(tree, extensions)
    else:
        node = normalize(tree)

    # --- Validate effective constraint against the tree ---
    validate_expression(effective_constraint, node)

    # --- Validate methods ---
    validate_methods(node, methods)

    # --- Collect extension label info ---
    ext_label_first_domains: dict[str, list[object]] = {}
    ext_label_occ_sets: dict[str, list[frozenset[object]]] = {}
    ext_label_first: dict[str, tuple[object, type]] = {}
    ext_label_enum_errors: dict[str, BaseException] = {}

    if extensions:
        _collect_ext_label_info(
            node,
            ext_label_first_domains,
            ext_label_occ_sets,
            ext_label_first,
            ext_label_enum_errors,
            extensions,
        )

    # Handle enum errors: "arbitrary" gets a sentinel; others re-raise.
    ext_label_arbitrary_infinite: dict[str, tuple[object, type]] = {}
    for label, exc in ext_label_enum_errors.items():
        method = methods.get(label, "all")
        if method == "arbitrary":
            ext_label_arbitrary_infinite[label] = ext_label_first[label]
        else:
            raise exc

    # Build override_domains (finite labels only) with ordered, intersected domains.
    override_domains: dict[str, list[object]] = {}
    ext_domain_orders: dict[str, list[object]] = {}
    for label in ext_label_first_domains:
        first_domain = ext_label_first_domains[label]
        occ_sets = ext_label_occ_sets[label]
        intersected_set: frozenset[object] = occ_sets[0]
        for s in occ_sets[1:]:
            intersected_set = intersected_set & s
        ordered = [v for v in first_domain if v in intersected_set]
        override_domains[label] = ordered
        ext_domain_orders[label] = ordered

    # Add sentinel placeholder domain for infinite-arb labels.
    for label in ext_label_arbitrary_infinite:
        override_domains[label] = [_INFINITE_SENTINEL]

    # --- Infer and fill integer bounds from effective_constraint ---
    bounds = infer_int_bounds(node, effective_constraint)
    if bounds:
        for _label, (lo, hi) in bounds.items():
            if lo > hi:
                return set()
        node = fill_int_bounds(node, bounds)

    # --- Validate tree ---
    validate_tree(node)

    # --- Fast path: no named nodes ---
    if not contains_name(node):
        satisfied = eval_expression(effective_constraint, {})
        if satisfied is not True:
            return set()
        ext_map = extensions if extensions else None
        return cast("set[GenerateT]", set(_values_node(node, ext_map)))

    # --- Build extension hooks for apply_methods ---
    ext_hooks: dict[str, tuple[object, Any, list[object]]] | None = None
    if ext_label_first:
        ext_hooks = {}
        for label, (owner, ext_type) in ext_label_first.items():
            if label not in ext_label_arbitrary_infinite:
                domain_order = ext_domain_orders.get(label, [])
                ext_hooks[label] = (owner, extensions[ext_type], domain_order)

    # Methods for the reduce step: exclude infinite-arb labels (handled separately).
    methods_for_reduce: Mapping[Label, Method] = (
        {k: v for k, v in methods.items() if k not in ext_label_arbitrary_infinite}
        if ext_label_arbitrary_infinite else methods
    )

    # --- Satisfying-assignment search ---
    assignments = search(
        node,
        effective_constraint,
        methods_for_reduce,
        override_domains if override_domains else None,
    )

    if not assignments:
        return set()

    # --- Apply super-method reductions ---
    reduced = apply_methods(
        assignments,
        methods_for_reduce,
        labels_in_order(node),
        ext_hooks,
    )

    if not reduced:
        return set()

    # --- Replace infinite-arb sentinels with actual values ---
    if ext_label_arbitrary_infinite:
        final_reduced = []
        for asgn in reduced:
            new_asgn = dict(asgn)
            for label, (owner, ext_type) in ext_label_arbitrary_infinite.items():
                if label in new_asgn and new_asgn[label] is _INFINITE_SENTINEL:
                    new_asgn[label] = extensions[ext_type].arbitrary(owner)
            final_reduced.append(new_asgn)
        reduced = final_reduced

    # --- Concretize each assignment into runtime values ---
    ext_map_for_concretize = extensions if extensions else None
    result: set[object] = set()
    for asgn in reduced:
        result.update(concretize(node, asgn, ext_map_for_concretize))

    return result  # type: ignore[return-value]
