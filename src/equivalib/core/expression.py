"""Expression AST for the new core."""

from __future__ import annotations

from dataclasses import dataclass
from typing import NoReturn, Optional, Sequence, Union


# ---------------------------------------------------------------------------
# Leaf nodes
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class BooleanConstant:
    """A literal boolean value."""

    value: bool


@dataclass(frozen=True)
class IntegerConstant:
    """A literal integer value."""

    value: int


@dataclass(frozen=True)
class Reference:
    """A reference to a leaf.

    ``path`` is a tuple of zero-based integer indices.  An empty path refers
    to the whole value bound to ``label``.
    By default, ``label`` is the root of the expression.
    """

    label: Optional[str]
    path: Sequence[int]


def reference(first: str | int, *rest: int) -> Reference:
    """Construct a ``Reference`` from either a label or a root index path.

    Examples:
    - ``reference("X")`` -> ``Reference("X", ())``
    - ``reference("T", 0, 1)`` -> ``Reference("T", (0, 1))``
    - ``reference(0, 1)`` -> ``Reference(None, (0, 1))``
    """
    if isinstance(first, str):
        return Reference(first, rest)
    return Reference(None, (first, *rest))


# ---------------------------------------------------------------------------
# Unary arithmetic
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Neg:
    """Arithmetic negation: ``-operand``."""

    operand: "ParsedExpression"


# ---------------------------------------------------------------------------
# Binary arithmetic
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Add:
    left: "ParsedExpression"
    right: "ParsedExpression"


@dataclass(frozen=True)
class Sub:
    left: "ParsedExpression"
    right: "ParsedExpression"


@dataclass(frozen=True)
class Mul:
    left: "ParsedExpression"
    right: "ParsedExpression"


@dataclass(frozen=True)
class FloorDiv:
    left: "ParsedExpression"
    right: "ParsedExpression"


@dataclass(frozen=True)
class Mod:
    left: "ParsedExpression"
    right: "ParsedExpression"


# ---------------------------------------------------------------------------
# Comparison
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Eq:
    left: "ParsedExpression"
    right: "ParsedExpression"


@dataclass(frozen=True)
class Ne:
    left: "ParsedExpression"
    right: "ParsedExpression"


@dataclass(frozen=True)
class Lt:
    left: "ParsedExpression"
    right: "ParsedExpression"


@dataclass(frozen=True)
class Le:
    left: "ParsedExpression"
    right: "ParsedExpression"


@dataclass(frozen=True)
class Gt:
    left: "ParsedExpression"
    right: "ParsedExpression"


@dataclass(frozen=True)
class Ge:
    left: "ParsedExpression"
    right: "ParsedExpression"


# ---------------------------------------------------------------------------
# Boolean combinators
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class And:
    left: "ParsedExpression"
    right: "ParsedExpression"


@dataclass(frozen=True)
class Or:
    left: "ParsedExpression"
    right: "ParsedExpression"


# ---------------------------------------------------------------------------
# Type aliases
# ---------------------------------------------------------------------------

ParsedExpression = Union[
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
]

RawExpression = str

Expression = Union[ParsedExpression, RawExpression]


# ---------------------------------------------------------------------------
# Convenience constructors
# ---------------------------------------------------------------------------

def BooleanExpression(value: bool) -> BooleanConstant:
    """Return ``BooleanConstant(value)``.

    ``BooleanExpression(True)`` is the canonical unconstrained expression.
    """
    return BooleanConstant(value)


def impossible(x: NoReturn) -> NoReturn:
    """Assert that a code branch is unreachable.

    Pass the narrowed value as ``x``; mypy will flag an error if any case
    in an exhaustive isinstance chain is missing.

    Usage::

        if isinstance(expr, BooleanConstant):
            ...
        elif isinstance(expr, IntegerConstant):
            ...
        else:
            impossible(expr)  # mypy: x has type Never here
    """
    raise TypeError(f"Unreachable branch reached with value: {x!r}")
