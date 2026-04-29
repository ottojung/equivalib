"""String-to-Expression parser for equivalib constraint expressions.

Grammar (informal)::

    expr     := or_expr
    or_expr  := and_expr ("or" and_expr)*
    and_expr := cmp_expr ("and" cmp_expr)*
    cmp_expr := add_expr (("==" | "!=" | "<" | "<=" | ">" | ">=") add_expr)?
    add_expr := mul_expr (("+" | "-") mul_expr)*
    mul_expr := unary (("*" | "//" | "%") unary)*
    unary    := "-" unary | atom
    atom     := "True" | "False" | INTEGER | ref | "(" expr ")"
    ref      := NAME ("[" INTEGER "]")* | ("[" INTEGER "]")+

Where ``NAME`` is a Python-style identifier that is not a reserved keyword
(``True``, ``False``, ``and``, ``or``), and ``INTEGER`` is a non-negative
decimal integer.

Reference semantics:

- ``X``         → ``reference("X")``       – named label, no path
- ``X[0]``      → ``reference("X", 0)``    – named label with one-level path
- ``X[0][1]``   → ``reference("X", 0, 1)`` – named label with multi-level path
- ``[0]``       → ``reference(0)``         – anonymous (root) reference
- ``[0][1]``    → ``reference(0, 1)``      – anonymous reference with path

Operator precedence (low → high):

1. ``or``
2. ``and``
3. ``==``, ``!=``, ``<``, ``<=``, ``>``, ``>=``
4. ``+``, ``-`` (binary)
5. ``*``, ``//``, ``%``
6. ``-`` (unary)
7. atoms and parentheses
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pyparsing as pp
from pyparsing import pyparsing_common as ppc

from equivalib.core.expression import (
    Add,
    And,
    BooleanConstant,
    Eq,
    Expression,
    FloorDiv,
    Ge,
    Gt,
    IntegerConstant,
    Le,
    Lt,
    Mod,
    Mul,
    Ne,
    Neg,
    Or,
    Sub,
    reference,
)

if TYPE_CHECKING:
    pass

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_CMP_OPS: dict[str, type] = {
    "==": Eq,
    "!=": Ne,
    "<=": Le,
    ">=": Ge,
    "<": Lt,
    ">": Gt,
}

_ADD_OPS: dict[str, type] = {
    "+": Add,
    "-": Sub,
}

_MUL_OPS: dict[str, type] = {
    "*": Mul,
    "//": FloorDiv,
    "%": Mod,
}


def _fold_binary(tokens: pp.ParseResults) -> Expression:
    """Fold a left-associative binary operator chain into nested AST nodes."""
    items = list(tokens[0])
    result: Expression = items[0]
    i = 1
    while i < len(items):
        op: str = items[i]
        right: Expression = items[i + 1]
        if op in _CMP_OPS:
            result = _CMP_OPS[op](result, right)
        elif op in _ADD_OPS:
            result = _ADD_OPS[op](result, right)
        elif op in _MUL_OPS:
            result = _MUL_OPS[op](result, right)
        elif op == "and":
            result = And(result, right)
        elif op == "or":
            result = Or(result, right)
        else:
            raise ValueError(f"Unknown operator: {op!r}")  # pragma: no cover
        i += 2
    return result


def _fold_unary_neg(tokens: pp.ParseResults) -> Expression:
    """Fold a chain of unary ``-`` operators (right-to-left) into ``Neg`` nodes."""
    items = list(tokens[0])
    # items is like ['-', '-', ..., atom]
    result: Expression = items[-1]
    for _ in items[:-1]:
        result = Neg(result)
    return result


# ---------------------------------------------------------------------------
# Grammar
# ---------------------------------------------------------------------------

# Reserved keywords must not be matched as identifiers.
_KW_TRUE = pp.Keyword("True")
_KW_FALSE = pp.Keyword("False")
_KW_AND = pp.Keyword("and")
_KW_OR = pp.Keyword("or")

# Non-negative integer literal → IntegerConstant
_integer: pp.ParserElement = ppc.integer.copy().set_parse_action(
    lambda t: IntegerConstant(int(t[0]))
)

# Subscript: [N]
_subscript: pp.ParserElement = pp.Suppress("[") + ppc.integer + pp.Suppress("]")

# Named reference: NAME optionally followed by [N][M]...
_identifier = ~_KW_TRUE + ~_KW_FALSE + ~_KW_AND + ~_KW_OR + pp.Word(
    pp.alphas + "_", pp.alphanums + "_"
)
_named_ref: pp.ParserElement = pp.Group(
    _identifier + pp.Group(pp.ZeroOrMore(_subscript))
).set_parse_action(
    lambda t: reference(t[0][0], *t[0][1].as_list())
)

# Anonymous reference: at least one [N], then optional more [M]...
_anon_ref: pp.ParserElement = pp.Group(
    pp.Group(pp.OneOrMore(_subscript))
).set_parse_action(
    lambda t: reference(*t[0][0].as_list())
)

# Boolean constants
_true: pp.ParserElement = _KW_TRUE.copy().set_parse_action(
    lambda: BooleanConstant(True)
)
_false: pp.ParserElement = _KW_FALSE.copy().set_parse_action(
    lambda: BooleanConstant(False)
)

# Full expression grammar with operator precedence via infixNotation.
# Operands: True, False, integer, named ref, anonymous ref (tried in order).
_expr: pp.ParserElement = pp.infix_notation(
    _true | _false | _integer | _named_ref | _anon_ref,
    [
        # Unary minus (right-associative, highest precedence)
        ("-", 1, pp.opAssoc.RIGHT, _fold_unary_neg),
        # Multiplicative
        (pp.one_of(["*", "//", "%"]), 2, pp.opAssoc.LEFT, _fold_binary),
        # Additive
        (pp.one_of(["+", "-"]), 2, pp.opAssoc.LEFT, _fold_binary),
        # Comparison (longer tokens first to avoid "<" eating "<=")
        (pp.one_of(["==", "!=", "<=", ">=", "<", ">"]), 2, pp.opAssoc.LEFT, _fold_binary),
        # Logical
        (_KW_AND, 2, pp.opAssoc.LEFT, _fold_binary),
        (_KW_OR, 2, pp.opAssoc.LEFT, _fold_binary),
    ],
)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def parse(text: str) -> Expression:
    """Parse a constraint string into an :data:`Expression` AST.

    Args:
        text: A constraint expression in the equivalib string syntax.

    Returns:
        The parsed :data:`Expression` AST node.

    Raises:
        ValueError: If ``text`` cannot be parsed as a valid expression.

    Examples::

        parse("True")                          # BooleanConstant(True)
        parse("X == Y")                        # Eq(Reference("X", ()), Reference("Y", ()))
        parse("X[0] != X[1]")                  # Ne(Reference("X", (0,)), Reference("X", (1,)))
        parse("[0] < [1]")                     # Lt(Reference(None, (0,)), Reference(None, (1,)))
        parse("X >= 0 and X <= 9")             # And(Ge(...), Le(...))
        parse("a * a + b * b == c * c")        # Eq(Add(Mul(a,a), Mul(b,b)), Mul(c,c))
    """
    try:
        result = _expr.parse_string(text, parse_all=True)
    except pp.ParseException as exc:
        raise ValueError(
            f"Failed to parse constraint expression: {text!r}\n"
            f"  {exc}"
        ) from exc
    expr: Expression = result[0]
    return expr
