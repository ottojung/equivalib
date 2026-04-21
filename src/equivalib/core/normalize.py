"""Normalize user-facing Python typing objects into the internal IR.

Entry point:
    normalize(t) -> IRNode
    normalize_with_extensions(t, extensions) -> IRNode
"""

from __future__ import annotations

import typing
import types
from typing import Mapping

from equivalib.core.name import Name
from equivalib.core.types import (
    NoneNode,
    BoolNode,
    LiteralNode,
    UnboundedIntNode,
    TupleNode,
    UnionNode,
    NamedNode,
    ExtensionLeafNode,
    IRNode,
)


def normalize(t: object) -> IRNode:
    """Normalize a type annotation ``t`` into an IR node.

    Raises ``ValueError`` for unsupported or malformed type expressions.
    """
    return _normalize(t, None)


def normalize_with_extensions(t: object, extensions: Mapping[type, object] | None) -> IRNode:
    """Normalize ``t`` into an IR node, honouring registered extensions.

    Extension-owned type values produce ``ExtensionLeafNode`` nodes instead of
    raising an unsupported-type error.
    """
    return _normalize(t, extensions)


def _lookup_extension(t: object, extensions: Mapping[type, object]) -> tuple[type, str] | None:
    """Return (extension_type, kind) if *t* is owned by a registered extension, else None."""
    # Rule 1: t is a type object and a direct key.
    if isinstance(t, type) and t in extensions:
        kind = "bool" if t is bool else ("int" if t is int else "opaque")
        return t, kind
    # Rule 2: type(t) is a key.
    if not isinstance(t, type) and type(t) in extensions:
        return type(t), "opaque"
    return None


def _normalize(t: object, extensions: Mapping[type, object] | None) -> IRNode:
    """Core normalize implementation shared by ``normalize`` and ``normalize_with_extensions``."""
    origin = typing.get_origin(t)
    args = typing.get_args(t)

    if origin is typing.Annotated:
        return _normalize_annotated(args[0], list(args[1:]), extensions)

    if t is type(None) or t is None:
        return NoneNode()

    if t is bool:
        if extensions is not None:
            hit = _lookup_extension(t, extensions)
            if hit is not None:
                ext_type, kind = hit
                return ExtensionLeafNode(owner=t, extension_type=ext_type, kind=kind)
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
        return TupleNode(tuple(_normalize(a, extensions) for a in args))

    if origin is typing.Union or origin is types.UnionType:
        options: list[IRNode] = []
        for a in args:
            options.append(_normalize(a, extensions))
        return UnionNode(tuple(options))

    # Check for extension-owned instance values (e.g. WARM, FINITE_REGEX).
    if extensions is not None:
        hit = _lookup_extension(t, extensions)
        if hit is not None:
            ext_type, kind = hit
            return ExtensionLeafNode(owner=t, extension_type=ext_type, kind=kind)
        # Custom (non-typing) value with no registered extension.
        raise ValueError(
            f"No extension registered for {t!r}: unsupported type expression. "
            "Register a matching extension or use a built-in type."
        )

    raise ValueError(
        f"Unsupported type expression: {t!r} — "
        "this appears to be a custom value with no registered extension. "
        "Register a matching extension or use a built-in supported type."
    )


def _normalize_annotated(base: object, metadata: list[object], extensions: Mapping[type, object] | None) -> IRNode:
    """Normalize an ``Annotated[base, *metadata]`` expression."""
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

    if base is int:
        if name is None:
            raise ValueError(
                "An 'int' in Annotated requires a Name(...) annotation. "
                "Use Annotated[int, Name('X')] and supply bounds via the constraint parameter."
            )
        inner: IRNode = UnboundedIntNode()
    else:
        inner = _normalize(base, extensions)

    if name is not None:
        return NamedNode(name.label, inner)

    return inner
