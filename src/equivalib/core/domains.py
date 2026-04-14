"""Finite denotation for name-free (unnamed) subtrees and label domains.

Public API:
    values(type_or_node) -> set      -- for use from API (accepts raw types)
    _values_node(node) -> frozenset  -- internal, operates on IR nodes
    domain_map(node) -> dict[str, frozenset]
"""

from __future__ import annotations

from typing import Type, TypeVar

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
from equivalib.core.normalize import normalize

ValuesT = TypeVar("ValuesT")


def values(t: Type[ValuesT]) -> set[ValuesT]:
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
    return set(_values_node(node))  # type: ignore[arg-type]


def _values_node(node: object) -> frozenset[object]:
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
    raise TypeError(f"Unknown IR node: {type(node)}")


def domain_map(node: object) -> dict[str, frozenset[object]]:
    """Return a mapping {label: frozenset} of domains for all named nodes.

    The domain of a label is the intersection of all individual occurrences of
    that label within the tree.

    If any label has an empty domain, the returned dict still contains it with
    an empty frozenset value.  The caller is responsible for checking emptiness.
    """
    occurrences: dict[str, list[frozenset[object]]] = {}
    _collect_occurrences(node, occurrences)

    result: dict[str, frozenset[object]] = {}
    for label, occ_list in occurrences.items():
        domain: frozenset[object] = occ_list[0]
        for occ in occ_list[1:]:
            domain = domain & occ
        result[label] = domain

    return result


def _collect_occurrences(node: object, out: dict[str, list[frozenset[object]]]) -> None:
    """Populate ``out`` with per-label occurrence lists."""
    if isinstance(node, (NoneNode, BoolNode, LiteralNode, IntRangeNode)):
        return
    if isinstance(node, TupleNode):
        for item in node.items:
            _collect_occurrences(item, out)
    elif isinstance(node, UnionNode):
        for opt in node.options:
            _collect_occurrences(opt, out)
    elif isinstance(node, NamedNode):
        label = node.label
        inner_vals = _values_node(node.inner)
        if label not in out:
            out[label] = []
        out[label].append(inner_vals)
        _collect_occurrences(node.inner, out)
    else:
        raise TypeError(f"Unknown IR node: {type(node)}")
