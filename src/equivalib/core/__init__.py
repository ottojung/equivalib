"""equivalib.core – the new value-tree generation engine.

Public API surface:
    generate         – the main generation function
    values           – finite denotation for name-free types
    parse            – parse a string expression into a ParsedExpression AST
    Name             – symbolic identity marker
    BooleanExpression – convenience constructor (returns BooleanConstant)
    reference        – convenience reference constructor
    mentioned_labels  – collect labels from an expression
    impossible       – exhaustive-match sentinel (NoReturn)

Extension base classes:
    Extension        – abstract base for custom leaf types
    Regex            – base for finite regex languages
    regex            – factory that creates a Regex subclass from a pattern string
    LineIntervalsSet – base for generating non-equivalent integer interval sets
    intervals        – factory that creates a LineIntervalsSet subclass from range and count

Expression AST constructors (ParsedExpression nodes):
    BooleanConstant, IntegerConstant, Reference
    Neg, Add, Sub, Mul, FloorDiv, Mod
    Eq, Ne, Lt, Le, Gt, Ge
    And, Or

Type aliases:
    ParsedExpression – Union of all expression AST node types
    RawExpression    – str (unparsed expression string)
    Expression       – Union[ParsedExpression, RawExpression]
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
    ParsedExpression,
    RawExpression,
    BooleanExpression,
    impossible,
)
from equivalib.core.api import generate
from equivalib.core.domains import values
from equivalib.core.cache import mentioned_labels
from equivalib.core.extension import Extension
from equivalib.core.regex import Regex, regex
from equivalib.core.line_intervals_set import LineIntervalsSet, intervals
from equivalib.core.parser import parse

__all__ = [
    "generate",
    "values",
    "parse",
    "Extension",
    "Regex",
    "regex",
    "LineIntervalsSet",
    "intervals",
    "Name",
    "Expression",
    "ParsedExpression",
    "RawExpression",
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
