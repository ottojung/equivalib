"""Normalize user-facing Python typing objects into the internal IR.

Entry point:
    normalize(t) -> IRNode
"""

from __future__ import annotations

import typing
import types

from equivalib.core.name import Name
from equivalib.core.types import (
    NoneNode,
    BoolNode,
    LiteralNode,
    UnboundedIntNode,
    TupleNode,
    UnionNode,
    NamedNode,
    ExtensionNode,
    IRNode,
)


def _try_extension(value: object, extensions: dict[type, object]) -> ExtensionNode | None:
    """Return an ExtensionNode if ``value`` matches a registered extension key, else None."""
    if isinstance(value, type):
        key: type | None = value if value in extensions else None
    else:
        t = type(value)
        key = t if t in extensions else None
    if key is None:
        return None
    kind = "bool" if key is bool else ("int" if key is int else "opaque")
    return ExtensionNode(key=key, owner=value, kind=kind)


def normalize(t: object, extensions: dict[type, object] | None = None) -> IRNode:
    """Normalize a type annotation ``t`` into an IR node.

    Raises ``ValueError`` for unsupported or malformed type expressions.
    """
    ext = extensions or {}

    # Check extension registry before any built-in checks so that extensions
    # can override built-in types (e.g. bool or int).
    ext_node = _try_extension(t, ext)
    if ext_node is not None:
        return ext_node

    origin = typing.get_origin(t)
    args = typing.get_args(t)

    if origin is typing.Annotated:
        return _normalize_annotated(args[0], list(args[1:]), ext)

    if t is type(None) or t is None:
        return NoneNode()

    if t is bool:
        return BoolNode()

    if t is int:
        raise ValueError(
            "Plain 'int' is not supported. "
            "Use Annotated[int, Name('X')] with bounds provided via the constraint parameter."
        )

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
        return UnionNode(tuple(LiteralNode(v) for v in args))

    if origin is tuple:
        return TupleNode(tuple(normalize(a, ext) for a in args))

    if origin is typing.Union or origin is types.UnionType:
        options: list[IRNode] = []
        for a in args:
            options.append(normalize(a, ext))
        return UnionNode(tuple(options))

    raise ValueError(
        f"unsupported type expression: {t!r}. "
        "If this is a custom leaf type, register it via the extensions= argument to generate()."
    )


def _normalize_annotated(base: object, metadata: list[object], extensions: dict[type, object] | None = None) -> IRNode:
    """Normalize an ``Annotated[base, *metadata]`` expression."""
    ext = extensions or {}
    names = [m for m in metadata if isinstance(m, Name)]
    unknown = [m for m in metadata if not isinstance(m, Name)]

    if unknown:
        raise ValueError(
            f"Unknown Annotated metadata: {unknown!r}. "
            "Only Name is supported."
        )
    if len(names) > 1:
        raise ValueError(
            f"Multiple Name annotations found: {names!r}. "
            "Only one Name is allowed per annotation."
        )

    name = names[0] if names else None

    if name is not None and not isinstance(name.label, str):
        raise ValueError(
            f"Name label must be a string, got {type(name.label).__name__!r}: {name.label!r}."
        )
    if name is not None and name.label == "":
        raise ValueError("Name label must not be empty.")

    # Check extension registry before the int special case.
    ext_node = _try_extension(base, ext)
    if ext_node is not None:
        inner: IRNode = ext_node
    elif base is int:
        if name is None:
            raise ValueError(
                "An 'int' in Annotated requires a Name(...) annotation. "
                "Use Annotated[int, Name('X')] and supply bounds via the constraint parameter."
            )
        inner: IRNode = UnboundedIntNode()
    else:
        inner = normalize(base, ext)

    if name is not None:
        return NamedNode(name.label, inner)

    return inner
