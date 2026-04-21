"""Extension support for equivalib.core.generate.

Defines the Extension protocol and helper functions for validating and
initialising extensions before generation.
"""

from __future__ import annotations

from typing import Any, Iterator, Mapping, Optional, Protocol, TypeVar

A = TypeVar("A")


class Extension(Protocol[A]):
    """Protocol that all extension objects must satisfy."""

    def initialize(self, tree: object, constraint: Any) -> Optional[Any]:
        """Called once before generation.  May return an extra boolean constraint or None."""
        ...

    def enumerate_all(self, owner: object) -> Iterator[A]:
        """Return all admissible values for the given owner leaf."""
        ...

    def arbitrary(self, owner: object, values: Any = None) -> Optional[A]:
        """Return one admissible value (canonical choice)."""
        ...

    def uniform_random(self, owner: object, weighted_values: Any = None) -> Optional[A]:
        """Return one admissible value using uniform-random semantics."""
        ...


_REQUIRED_METHODS = ("initialize", "enumerate_all", "arbitrary", "uniform_random")


def validate_extensions(extensions: object) -> None:
    """Raise TypeError/ValueError if ``extensions`` is invalid.

    Checks:
    - extensions is a Mapping (or None)
    - every key is a type object
    - every value provides all four required methods
    """
    if extensions is None:
        return

    if not isinstance(extensions, Mapping):
        raise TypeError(
            f"'extensions' must be a Mapping[type, Extension] or None, "
            f"got {type(extensions).__name__!r}."
        )

    for key, ext in extensions.items():
        if not isinstance(key, type):
            raise TypeError(
                f"Each extension registry key must be a type object, "
                f"got {type(key).__name__!r}: {key!r}."
            )
        for method_name in _REQUIRED_METHODS:
            if not hasattr(ext, method_name) or not callable(getattr(ext, method_name)):
                raise TypeError(
                    f"Extension for {key!r} is missing required method {method_name!r}."
                )


from equivalib.core.expression import (
    BooleanConstant, IntegerConstant, Reference, Neg,
    Add, Sub, Mul, FloorDiv, Mod,
    Eq, Ne, Lt, Le, Gt, Ge, And, Or,
)

_ALL_EXPRESSION_TYPES = (
    BooleanConstant, IntegerConstant, Reference, Neg,
    Add, Sub, Mul, FloorDiv, Mod,
    Eq, Ne, Lt, Le, Gt, Ge, And, Or,
)
_BOOL_EXPRESSION_TYPES = (BooleanConstant, Reference, Eq, Ne, Lt, Le, Gt, Ge, And, Or)


def _is_expression_node(obj: object) -> bool:
    """Return True if *obj* is any recognized Expression AST node."""
    return isinstance(obj, _ALL_EXPRESSION_TYPES)


def _is_boolean_expr(obj: object) -> bool:
    """Return True if *obj* is structurally a boolean-valued Expression."""
    # Reference may or may not be boolean - we accept it (label type is
    # checked later during validate_expression with the full tree context).
    return isinstance(obj, _BOOL_EXPRESSION_TYPES)


def run_initialize(
    extensions: Mapping[type, Any],
    tree: object,
    constraint: Any,
) -> list[Any]:
    """Call ``initialize`` on every registered extension.

    Returns a list of non-None expressions returned by the extensions.
    Raises TypeError if any extension returns a non-expression or a
    non-boolean expression.
    """
    extras: list[Any] = []
    for ext_type, extension in extensions.items():
        result = extension.initialize(tree, constraint)
        if result is None:
            continue
        if not _is_expression_node(result):
            raise TypeError(
                f"Extension for {ext_type!r} returned a non-expression from initialize(): "
                f"got {type(result).__name__!r}: {result!r}."
            )
        if not _is_boolean_expr(result):
            raise TypeError(
                f"Extension for {ext_type!r} returned a non-boolean expression from "
                f"initialize(): {result!r}."
            )
        extras.append(result)

    return extras
