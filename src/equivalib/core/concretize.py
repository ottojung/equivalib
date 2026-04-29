from __future__ import annotations

from typing import Mapping

from equivalib.core.expression import impossible
from equivalib.core.types import (
    BoolNode,
    ExtensionNode,
    IntRangeNode,
    IRNode,
    LiteralNode,
    NamedNode,
    NoneNode,
    TupleNode,
    UnboundedIntNode,
    UnionNode,
)


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
                existing + (v,)
                for existing in result
                for v in item_vals  # type: ignore[operator]
            )
        return result
    if isinstance(node, UnionNode):
        result = frozenset()
        for opt in node.options:
            result = result | concretize(opt, assignment)
        return result
    impossible(node)
