"""Normalize user-facing Python typing objects into the internal IR.

Entry point:
    normalize(t) -> IRNode
"""

from __future__ import annotations

import typing
from typing import Any

from equivalib.value_range import ValueRange
from equivalib.core.name import Name
from equivalib.core.types import (
    NoneNode,
    BoolNode,
    LiteralNode,
    IntRangeNode,
    TupleNode,
    UnionNode,
    NamedNode,
)


def normalize(t: Any) -> object:
    """Normalize a type annotation ``t`` into an IR node.

    Raises ``ValueError`` for unsupported or malformed type expressions.
    """
    # Peel off Annotated wrapper first so we can inspect metadata.
    origin = typing.get_origin(t)
    args = typing.get_args(t)

    if origin is typing.Annotated:
        return _normalize_annotated(args[0], list(args[1:]))

    # --- Primitive types ---
    if t is type(None) or t is None:
        return NoneNode()

    if t is bool:
        return BoolNode()

    if t is int:
        raise ValueError(
            "Plain 'int' is not supported in the new core. "
            "Use Annotated[int, ValueRange(a, b)] instead."
        )

    # --- Literal ---
    if origin is typing.Literal:
        _SUPPORTED_LITERAL_TYPES = (type(None), bool, int, str)
        for v in args:
            if not isinstance(v, _SUPPORTED_LITERAL_TYPES):
                raise ValueError(
                    f"Literal value {v!r} has unsupported type {type(v).__name__!r}. "
                    f"Only None, bool, int, and str are supported in Literal[...]."
                )
        if len(args) == 1:
            return LiteralNode(args[0])
        # Multi-value Literal: expand into UnionNode
        return UnionNode(tuple(LiteralNode(v) for v in args))

    # --- Tuple ---
    if origin is tuple:
        return TupleNode(tuple(normalize(a) for a in args))

    # --- Union ---
    if origin is typing.Union:
        options = []
        for a in args:
            options.append(normalize(a))
        return UnionNode(tuple(options))

    raise ValueError(f"Unsupported type expression: {t!r}")


def _normalize_annotated(base: Any, metadata: list[Any]) -> object:
    """Normalize an ``Annotated[base, *metadata]`` expression."""
    value_ranges = [m for m in metadata if isinstance(m, ValueRange)]
    names = [m for m in metadata if isinstance(m, Name)]
    unknown = [m for m in metadata if not isinstance(m, (ValueRange, Name))]

    if unknown:
        raise ValueError(
            f"Unknown Annotated metadata in new core: {unknown!r}. "
            "Only ValueRange and Name are supported."
        )
    if len(value_ranges) > 1:
        raise ValueError(
            f"Multiple ValueRange annotations found: {value_ranges!r}. "
            "Only one ValueRange is allowed per annotation."
        )
    if len(names) > 1:
        raise ValueError(
            f"Multiple Name annotations found: {names!r}. "
            "Only one Name is allowed per annotation."
        )

    vr = value_ranges[0] if value_ranges else None
    name = names[0] if names else None

    if name is not None and name.label == "":
        raise ValueError("Name label must not be empty.")

    # Determine the inner node.
    if vr is not None:
        # The base must be int.
        if base is not int:
            raise ValueError(
                f"ValueRange can only be applied to 'int', not {base!r}."
            )
        if vr.min > vr.max:
            raise ValueError(
                f"ValueRange has invalid bounds: min={vr.min} > max={vr.max}."
            )
        inner: object = IntRangeNode(vr.min, vr.max)
    else:
        inner = normalize(base)

    if name is not None:
        return NamedNode(name.label, inner)

    return inner
