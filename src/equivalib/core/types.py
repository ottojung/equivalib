"""Normalized internal representation for the new core.

After parsing a user-supplied ``Type[T]``, all further processing operates on
these immutable IR nodes rather than on raw ``typing`` objects.

Kind-rank table (used for canonical total order, documented here):
    0 – None
    1 – bool
    2 – int / float (numeric scalars)
    3 – str
    4 – tuple
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Tuple as TypingTuple


# ---------------------------------------------------------------------------
# IR nodes
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class NoneNode:
    """Represents the singleton ``None`` value."""


@dataclass(frozen=True)
class BoolNode:
    """Represents the boolean domain ``{True, False}``."""


@dataclass(frozen=True)
class LiteralNode:
    """Represents a singleton domain ``{value}``."""

    value: object

    def __hash__(self) -> int:
        try:
            return hash(("LiteralNode", self.value))
        except TypeError:
            return hash(("LiteralNode", id(self.value)))

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, LiteralNode):
            return NotImplemented
        return self.value == other.value  # type: ignore[no-any-return]


@dataclass(frozen=True)
class IntRangeNode:
    """Represents a bounded integer domain ``{min_value, ..., max_value}``."""

    min_value: int
    max_value: int


@dataclass(frozen=True)
class TupleNode:
    """Represents a product type."""

    items: TypingTuple["IRNode", ...]


@dataclass(frozen=True)
class UnionNode:
    """Represents a sum type."""

    options: TypingTuple["IRNode", ...]


@dataclass(frozen=True)
class NamedNode:
    """Wraps a subtree and gives it a symbolic label."""

    label: str
    inner: "IRNode"


IRNode = object  # Union of all IR node types (kept as ``object`` for compat)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def labels(node: object) -> frozenset:
    """Return all labels used within ``node``."""
    if isinstance(node, (NoneNode, BoolNode, LiteralNode, IntRangeNode)):
        return frozenset()
    if isinstance(node, TupleNode):
        result: frozenset = frozenset()
        for item in node.items:
            result = result | labels(item)
        return result
    if isinstance(node, UnionNode):
        result = frozenset()
        for opt in node.options:
            result = result | labels(opt)
        return result
    if isinstance(node, NamedNode):
        return frozenset({node.label}) | labels(node.inner)
    raise TypeError(f"Unknown IR node: {type(node)}")


def contains_name(node: object) -> bool:
    """Return True iff ``node`` contains at least one ``NamedNode``."""
    return bool(labels(node))


def tree_shape(node: object) -> object:
    """Return a structural descriptor of the node for address validation.

    The shape of a ``NamedNode`` is the shape of its inner node (not of the
    NamedNode itself), because address paths look through the name.
    """
    if isinstance(node, (NoneNode, BoolNode, LiteralNode, IntRangeNode)):
        return node
    if isinstance(node, TupleNode):
        return TupleNode(tuple(tree_shape(i) for i in node.items))
    if isinstance(node, UnionNode):
        return UnionNode(tuple(tree_shape(o) for o in node.options))
    if isinstance(node, NamedNode):
        return tree_shape(node.inner)
    raise TypeError(f"Unknown IR node: {type(node)}")
