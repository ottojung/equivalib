"""Finite denotation for name-free (unnamed) subtrees and label domains.

Public API:
    values(type_or_node) -> set      -- for use from API (accepts raw types)
    _values_node(node) -> frozenset  -- internal, operates on IR nodes
    domain_map(node) -> dict[str, list[object]]
"""

from __future__ import annotations

from equivalib.core.expression import impossible
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
)
from equivalib.core.normalize import normalize


def values(t: object) -> set[object]:
    """Return the finite denotation of type ``t``.

    Raises ``ValueError`` if the type contains any named nodes.
    This is the public helper exported from ``equivalib.core``.
    """
    node = normalize(t)
    if contains_name(node):
        raise ValueError(
            "values() does not accept named trees. "
            "Use generate() for trees that contain Name annotations."
        )
    return set(_values_node(node))


def _values_node(node: IRNode) -> frozenset[object]:
    """Return the finite denotation of ``node`` (IR-level, internal)."""
    if isinstance(node, NoneNode):
        return frozenset({None})
    if isinstance(node, BoolNode):
        return frozenset({True, False})
    if isinstance(node, LiteralNode):
        return frozenset({node.value})
    if isinstance(node, IntRangeNode):
        return frozenset(range(node.min_value, node.max_value + 1))
    if isinstance(node, TupleNode):
        result: frozenset[object] = frozenset({()})
        for item in node.items:
            item_vals = _values_node(item)
            result = frozenset(
                existing + (v,) for existing in result for v in item_vals  # type: ignore[operator]
            )
        return result
    if isinstance(node, UnionNode):
        result = frozenset()
        for opt in node.options:
            result = result | _values_node(opt)
        return result
    if isinstance(node, NamedNode):
        # For domain computation purposes, return the denotation of the inner
        # node (ignoring the name).
        return _values_node(node.inner)
    impossible(node)


def _tag_value(v: object) -> object:
    """Return a recursively type-tagged version of ``v`` for type-aware comparison.

    Python's ``True == 1`` and ``False == 0`` propagate into tuples, so
    ``(True,) == (1,)`` in plain Python.  This function embeds ``type(v)``
    into the representation so that values of different types always compare
    as distinct, even when nested inside tuples.
    """
    if isinstance(v, bool):
        # bool is a subclass of int; check it first.
        return (bool, v)
    if isinstance(v, int):
        return (int, v)
    if isinstance(v, tuple):
        return (tuple, tuple(_tag_value(elem) for elem in v))
    return (type(v), v)


def _untag_value(tagged: object) -> object:
    """Reverse the transformation applied by ``_tag_value``.

    Given a tagged value ``(type_tag, payload)``, returns the original
    Python value. For tuple payloads, recursively untags each element.
    """
    if not isinstance(tagged, tuple) or len(tagged) != 2:
        raise TypeError(f"Expected tagged pair, got {tagged!r}")
    t, v = tagged
    if t is tuple:
        if not isinstance(v, tuple):
            raise TypeError(f"Expected tuple payload for tuple tag, got {v!r}")
        return tuple(_untag_value(e) for e in v)
    return v


def _values_node_tagged(node: IRNode) -> frozenset[object]:
    """Return the finite denotation of ``node`` as a frozenset of tagged values.

    Uses ``_tag_value`` recursively so that bool/int-equal values (``True``
    vs ``1``, ``(True,)`` vs ``(1,)`` etc.) are preserved as distinct elements.
    This avoids Python's set-level conflation of ``True == 1``.
    """
    if isinstance(node, NoneNode):
        return frozenset({_tag_value(None)})
    if isinstance(node, BoolNode):
        return frozenset({_tag_value(True), _tag_value(False)})
    if isinstance(node, LiteralNode):
        return frozenset({_tag_value(node.value)})
    if isinstance(node, IntRangeNode):
        return frozenset(_tag_value(i) for i in range(node.min_value, node.max_value + 1))
    if isinstance(node, TupleNode):
        # Build a frozenset of row-tuples made from tagged element values.
        # Each row is then wrapped in a tuple tag to form a tagged-tuple value.
        tagged_rows: frozenset[tuple[object, ...]] = frozenset({()})
        for item in node.items:
            item_tagged_vals = _values_node_tagged(item)
            tagged_rows = frozenset(
                existing + (tv,) for existing in tagged_rows for tv in item_tagged_vals
            )
        return frozenset((tuple, row) for row in tagged_rows)
    if isinstance(node, UnionNode):
        # Plain frozenset union works correctly here because elements are
        # already tagged: (bool, True) and (int, 1) are distinct.
        result: frozenset[object] = frozenset()
        for opt in node.options:
            result = result | _values_node_tagged(opt)
        return result
    if isinstance(node, NamedNode):
        return _values_node_tagged(node.inner)
    impossible(node)


def _type_aware_intersect(
    a: frozenset[object],
    b: frozenset[object],
) -> frozenset[object]:
    """Return the intersection of ``a`` and ``b`` with recursive type-awareness.

    Python's built-in ``==`` conflates ``bool`` and ``int``
    (``True == 1``, ``False == 0``), and this propagates into tuples
    (``(True,) == (1,)``).  This function uses ``_tag_value`` to enforce
    strict recursive type equality at every nesting level.

    Note: ``domain_map`` uses the more efficient ``_values_node_tagged`` +
    plain set intersection internally; this function is provided as a
    standalone type-aware intersection utility.
    """
    tag_to_val = {_tag_value(v): v for v in a}
    b_tags = frozenset(_tag_value(v) for v in b)
    return frozenset(tag_to_val[t] for t in tag_to_val if t in b_tags)


def domain_map(node: IRNode) -> dict[str, list[object]]:
    """Return a mapping {label: list} of type-distinct domain values.

    The domain for each label is the intersection of all per-occurrence
    denotations, computed with full recursive type-awareness using tagged
    frozensets internally.  The returned list can contain both ``True``
    (bool) and ``1`` (int) as distinct elements, unlike a Python frozenset
    which would collapse them due to ``True == 1``.

    If any label has an empty domain, the returned dict still contains it
    with an empty list.  The caller is responsible for checking emptiness.
    """
    occurrences: dict[str, list[frozenset[object]]] = {}
    _collect_occurrences_tagged(node, occurrences)

    result: dict[str, list[object]] = {}
    for label, occ_list in occurrences.items():
        # All elements in occ_list are tagged frozensets; plain set
        # intersection distinguishes bool from int without double-tagging.
        tagged_domain: frozenset[object] = occ_list[0]
        for occ in occ_list[1:]:
            tagged_domain = tagged_domain & occ
        result[label] = [_untag_value(tv) for tv in tagged_domain]

    return result


def _collect_occurrences_tagged(
    node: IRNode,
    out: dict[str, list[frozenset[object]]],
) -> None:
    """Populate ``out`` with per-label tagged occurrence frozensets."""
    if isinstance(node, (NoneNode, BoolNode, LiteralNode, IntRangeNode)):
        return
    if isinstance(node, TupleNode):
        for item in node.items:
            _collect_occurrences_tagged(item, out)
    elif isinstance(node, UnionNode):
        for opt in node.options:
            _collect_occurrences_tagged(opt, out)
    elif isinstance(node, NamedNode):
        label = node.label
        inner_tagged_vals = _values_node_tagged(node.inner)
        if label not in out:
            out[label] = []
        out[label].append(inner_tagged_vals)
        _collect_occurrences_tagged(node.inner, out)
    else:
        impossible(node)
