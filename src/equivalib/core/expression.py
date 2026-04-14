"""Expression AST for the new core."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Union


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
    """A reference to a named label, with an optional address path into tuples.

    ``path`` is a tuple of zero-based integer indices.  An empty path refers
    to the whole value bound to ``label``.
    """

    label: str
    path: tuple[int, ...] = ()


# ---------------------------------------------------------------------------
# Unary arithmetic
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Neg:
    """Arithmetic negation: ``-operand``."""

    operand: "Expression"


# ---------------------------------------------------------------------------
# Binary arithmetic
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Add:
    left: "Expression"
    right: "Expression"


@dataclass(frozen=True)
class Sub:
    left: "Expression"
    right: "Expression"


@dataclass(frozen=True)
class Mul:
    left: "Expression"
    right: "Expression"


@dataclass(frozen=True)
class FloorDiv:
    left: "Expression"
    right: "Expression"


@dataclass(frozen=True)
class Mod:
    left: "Expression"
    right: "Expression"


# ---------------------------------------------------------------------------
# Comparison
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Eq:
    left: "Expression"
    right: "Expression"


@dataclass(frozen=True)
class Ne:
    left: "Expression"
    right: "Expression"


@dataclass(frozen=True)
class Lt:
    left: "Expression"
    right: "Expression"


@dataclass(frozen=True)
class Le:
    left: "Expression"
    right: "Expression"


@dataclass(frozen=True)
class Gt:
    left: "Expression"
    right: "Expression"


@dataclass(frozen=True)
class Ge:
    left: "Expression"
    right: "Expression"


# ---------------------------------------------------------------------------
# Boolean combinators
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class And:
    left: "Expression"
    right: "Expression"


@dataclass(frozen=True)
class Or:
    left: "Expression"
    right: "Expression"


# ---------------------------------------------------------------------------
# Type alias (documentation only)
# ---------------------------------------------------------------------------

Expression = Union[
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


# ---------------------------------------------------------------------------
# Convenience constructor
# ---------------------------------------------------------------------------

def BooleanExpression(value: bool) -> BooleanConstant:
    """Return ``BooleanConstant(value)``.

    ``BooleanExpression(True)`` is the canonical unconstrained expression.
    """
    return BooleanConstant(value)
