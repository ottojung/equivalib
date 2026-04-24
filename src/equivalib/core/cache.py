"""Caching for the new core.

Two mandatory caches:
    1. Unnamed subtree denotation cache (keyed by node).
    2. Guaranteed-cacheable subtree generation cache (keyed by subtree + methods).

Public API:
    mentioned_labels(expr) -> set[str]
    is_label_closed(subtree, whole_tree) -> bool
    is_constraint_independent(subtree, constraint) -> bool
    is_guaranteed_cacheable(subtree, whole_tree, constraint) -> bool
    CacheStats
    UnnamedCache
    GenerationCache
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from equivalib.core.types import (
    NoneNode,
    BoolNode,
    LiteralNode,
    IntRangeNode,
    UnboundedIntNode,
    ExtensionNode,
    TupleNode,
    UnionNode,
    NamedNode,
    IRNode,
    labels as tree_labels,
    contains_name,
)
from equivalib.core.expression import (
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
    Expression,
    impossible,
)


# ---------------------------------------------------------------------------
# mentioned_labels
# ---------------------------------------------------------------------------

def mentioned_labels(expr: Expression) -> set[str]:
    """Return the set of label strings referenced in ``expr``."""
    result: set[str] = set()
    _collect_labels(expr, result)
    return result


def _collect_labels(expr: Expression, out: set[str]) -> None:
    if isinstance(expr, (BooleanConstant, IntegerConstant)):
        return
    if isinstance(expr, Reference):
        out.add(expr.label)
        return
    if isinstance(expr, Neg):
        _collect_labels(expr.operand, out)
        return
    if isinstance(expr, (Add, Sub, Mul, FloorDiv, Mod, Eq, Ne, Lt, Le, Gt, Ge, And, Or)):
        _collect_labels(expr.left, out)
        _collect_labels(expr.right, out)
        return
    impossible(expr)


# ---------------------------------------------------------------------------
# Cache helpers
# ---------------------------------------------------------------------------

def is_label_closed(subtree: IRNode, whole_tree: IRNode) -> bool:
    """True iff every label in ``subtree`` is not used outside ``subtree``.

    That is, no label in ``subtree`` also appears anywhere else in
    ``whole_tree``.
    """
    subtree_labels = tree_labels(subtree)
    if not subtree_labels:
        return True  # unnamed subtrees are trivially label-closed
    # A subtree is label-closed when none of its labels appear in the rest of
    # the tree (i.e., outside of the subtree itself).
    rest_labels = _labels_outside(subtree, whole_tree)
    return not (subtree_labels & rest_labels)


def _labels_outside(subtree: IRNode, node: IRNode) -> frozenset[str]:
    """Return labels in ``node`` that are NOT in ``subtree`` (using object identity)."""
    if node is subtree:
        return frozenset()
    if isinstance(node, (NoneNode, BoolNode, LiteralNode, IntRangeNode, UnboundedIntNode, ExtensionNode)):
        return frozenset()
    if isinstance(node, TupleNode):
        result: frozenset[str] = frozenset()
        for item in node.items:
            result = result | _labels_outside(subtree, item)
        return result
    if isinstance(node, UnionNode):
        result = frozenset()
        for opt in node.options:
            result = result | _labels_outside(subtree, opt)
        return result
    if isinstance(node, NamedNode):
        return frozenset({node.label}) | _labels_outside(subtree, node.inner)
    impossible(node)


def is_constraint_independent(subtree: IRNode, constraint: Expression) -> bool:
    """True iff no label in ``subtree`` is referenced in ``constraint``."""
    sub_labels = tree_labels(subtree)
    if not sub_labels:
        return True
    expr_labels = mentioned_labels(constraint)
    return not (sub_labels & expr_labels)


def is_guaranteed_cacheable(subtree: IRNode, whole_tree: IRNode, constraint: Expression) -> bool:
    """True iff ``subtree`` is safe to cache independently.

    Guaranteed-cacheable cases (from the spec):
        1. Unnamed subtrees.
        2. Subtrees that are both label-closed and constraint-independent.
    """
    if not contains_name(subtree):
        return True
    return is_label_closed(subtree, whole_tree) and is_constraint_independent(subtree, constraint)


def _cache_key(subtree: IRNode, methods: Mapping[str, str]) -> tuple[object, tuple[tuple[str, str], ...]]:
    """Return a hashable cache key for a guaranteed-cacheable subtree."""
    sub_labels = tree_labels(subtree)
    restricted = tuple(sorted((k, v) for k, v in methods.items() if k in sub_labels))
    return (subtree, restricted)


# ---------------------------------------------------------------------------
# Cache statistics
# ---------------------------------------------------------------------------

@dataclass
class CacheStats:
    unnamed_hits: int = 0
    unnamed_misses: int = 0
    named_hits: int = 0
    named_misses: int = 0

    @property
    def total_hits(self) -> int:
        return self.unnamed_hits + self.named_hits

    @property
    def total_misses(self) -> int:
        return self.unnamed_misses + self.named_misses


# ---------------------------------------------------------------------------
# Cache stores
# ---------------------------------------------------------------------------

#: Sentinel returned by ``UnnamedCache.get`` and ``GenerationCache.get`` on a
#: cache miss.  Callers must check ``result is CACHE_MISS`` rather than
#: ``result is None`` so that a legitimately cached ``None`` value can be
#: distinguished from an absent entry.
CACHE_MISS: object = object()


class UnnamedCache:
    """Cache for unnamed (name-free) subtree denotations."""

    def __init__(self, stats: CacheStats) -> None:
        self._store: dict[IRNode, object] = {}
        self._stats = stats

    def get(self, node: IRNode) -> object:
        """Return the cached value for *node*, or ``CACHE_MISS`` on a miss."""
        key = node
        if key in self._store:
            self._stats.unnamed_hits += 1
            return self._store[key]
        self._stats.unnamed_misses += 1
        return CACHE_MISS

    def set(self, node: IRNode, value: object) -> None:
        self._store[node] = value


class GenerationCache:
    """Cache for guaranteed-cacheable subtree generation results."""

    def __init__(self, stats: CacheStats) -> None:
        self._store: dict[tuple[object, tuple[tuple[str, str], ...]], object] = {}
        self._stats = stats

    def get(self, subtree: IRNode, methods: Mapping[str, str]) -> object:
        """Return the cached value, or ``CACHE_MISS`` on a miss."""
        key = _cache_key(subtree, methods)
        if key in self._store:
            self._stats.named_hits += 1
            return self._store[key]
        self._stats.named_misses += 1
        return CACHE_MISS

    def set(self, subtree: IRNode, methods: Mapping[str, str], value: object) -> None:
        key = _cache_key(subtree, methods)
        self._store[key] = value
