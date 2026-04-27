"""equivalib.core – the new value-tree generation engine.

Public API surface:
    generate         – the main generation function
    values           – finite denotation for name-free types
    Name             – symbolic identity marker
    BooleanExpression – convenience constructor (returns BooleanConstant)
    reference        – convenience reference constructor
    mentioned_labels  – collect labels from an expression
    impossible       – exhaustive-match sentinel (NoReturn)

Expression AST constructors:
    BooleanConstant, IntegerConstant, Reference
    Neg, Add, Sub, Mul, FloorDiv, Mod
    Eq, Ne, Lt, Le, Gt, Ge
    And, Or

Type aliases:
    Expression       – Union of all expression node types
"""

from equivalib.core.name import Name
from equivalib.core.expression import (
    BooleanConstant,
    IntegerConstant,
    Reference,
    reference,
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
    BooleanExpression,
    impossible,
)
from equivalib.core.api import generate
from equivalib.core.domains import values
from equivalib.core.cache import mentioned_labels
from equivalib.core.extension import Extension
from equivalib.core.regex import Regex

__all__ = [
    "generate",
    "values",
    "Extension",
    "Regex",
    "Name",
    "Expression",
    "BooleanExpression",
    "BooleanConstant",
    "IntegerConstant",
    "Reference",
    "reference",
    "Neg",
    "Add",
    "Sub",
    "Mul",
    "FloorDiv",
    "Mod",
    "Eq",
    "Ne",
    "Lt",
    "Le",
    "Gt",
    "Ge",
    "And",
    "Or",
    "mentioned_labels",
    "impossible",
]
