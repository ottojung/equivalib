"""BNF-based expression parser for the new core.

Parses string expressions into ``ParsedExpression`` AST nodes.

Grammar (EBNF-style, maps 1-to-1 to the lark BNF grammar below):

    expr        = or_expr
    or_expr     = and_expr ("or" and_expr)*
    and_expr    = cmp_expr ("and" cmp_expr)*
    cmp_expr    = sum_expr (cmp_op sum_expr)*
    cmp_op      = "==" | "!=" | "<" | "<=" | ">" | ">="
    sum_expr    = mul_expr (("+"|"-") mul_expr)*
    mul_expr    = neg_expr (("*"|"//"|"%") neg_expr)*
    neg_expr    = "-" neg_expr | atom
    atom        = "true" | "false" | INT | reference | "(" expr ")"
    reference   = LABEL ("[" INT "]")*
               | ("[" INT "]")+
    LABEL       = /[A-Za-z_][A-Za-z0-9_]*/
    INT         = /0|[1-9][0-9]*/

Operator precedence (lowest to highest):
    or, and, comparison (==, !=, <, <=, >, >=), +/-, *///%,  unary -

Comparisons are associative (Python-style chaining): ``1 < x < 10`` is
parsed as ``And(Lt(1, x), Lt(x, 10))``.  Each consecutive pair of operands
is compared with its intervening operator; all pairs are joined with ``And``.

Reserved identifiers (not valid as label names in string expressions):
``true``, ``false``, ``and``, ``or``, ``self``.
Label identifiers that spell a reserved keyword are not supported in string
expressions; use the ``ParsedExpression`` AST constructors directly instead.

Special identifier ``self``:
    ``self`` is a reserved root-reference identifier.  It refers to the root
    of the type tree being generated and is equivalent to an anonymous
    ``Reference(None, path)`` node.  It may be followed by index suffixes:

        ``self``       →  ``Reference(None, ())``
        ``self[0]``    →  ``Reference(None, (0,))``
        ``self[0][1]`` →  ``Reference(None, (0, 1))``

    These are identical to the anonymous index references ``[0]``, ``[0][1]``,
    etc., except that ``self`` (without any index suffix) also refers to the
    root value itself.  Use ``self`` when you want to constrain the generated
    value directly without introducing a ``Name(...)`` annotation.

Empty string constraint:
    An empty (or whitespace-only) string is accepted and is equivalent to
    ``BooleanConstant(True)`` (the always-true, unconstrained case).
"""

from __future__ import annotations

import functools
from typing import cast

from lark import Lark, Token, Transformer

from equivalib.core.expression import (
    Add,
    And,
    BooleanConstant,
    Eq,
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
    ParsedExpression,
    Reference,
    Sub,
)

_GRAMMAR = r"""
    start: expr

    ?expr: or_expr

    ?or_expr: and_expr
            | or_expr "or" and_expr  -> or_

    ?and_expr: cmp_expr
             | and_expr "and" cmp_expr  -> and_

    ?cmp_expr: sum_expr
             | cmp_chain

    cmp_chain: sum_expr (CMP_OP sum_expr)+

    CMP_OP: "==" | "!=" | "<=" | ">=" | "<" | ">"

    ?sum_expr: mul_expr
             | sum_expr "+" mul_expr  -> add
             | sum_expr "-" mul_expr  -> sub

    ?mul_expr: neg_expr
             | mul_expr "*" neg_expr   -> mul
             | mul_expr "//" neg_expr  -> floordiv
             | mul_expr "%" neg_expr   -> mod

    ?neg_expr: atom
             | "-" neg_expr  -> neg

    ?atom: "true"           -> true_
         | "false"          -> false_
         | INT              -> integer
         | reference
         | "(" expr ")"

    reference: LABEL ("[" INT "]")*  -> labeled_ref
             | ("[" INT "]")+        -> indexed_ref

    LABEL: /[A-Za-z_][A-Za-z0-9_]*/
    INT: /0|[1-9][0-9]*/

    %ignore /\s+/
"""


class _ExprTransformer(Transformer):  # type: ignore[type-arg]
    def start(self, args: list[ParsedExpression]) -> ParsedExpression:
        return args[0]

    def true_(self, _args: list[object]) -> BooleanConstant:
        return BooleanConstant(True)

    def false_(self, _args: list[object]) -> BooleanConstant:
        return BooleanConstant(False)

    def integer(self, args: list[Token]) -> IntegerConstant:
        return IntegerConstant(int(str(args[0])))

    def labeled_ref(self, args: list[Token]) -> Reference:
        label = str(args[0])
        path = tuple(int(str(t)) for t in args[1:])
        if label == "self":
            # 'self' is the reserved root-reference identifier: it denotes the
            # root of the type tree and is equivalent to Reference(None, path).
            return Reference(None, path)
        return Reference(label, path)

    def indexed_ref(self, args: list[Token]) -> Reference:
        path = tuple(int(str(t)) for t in args)
        return Reference(None, path)

    def neg(self, args: list[ParsedExpression]) -> Neg:
        return Neg(args[0])

    def add(self, args: list[ParsedExpression]) -> Add:
        return Add(args[0], args[1])

    def sub(self, args: list[ParsedExpression]) -> Sub:
        return Sub(args[0], args[1])

    def mul(self, args: list[ParsedExpression]) -> Mul:
        return Mul(args[0], args[1])

    def floordiv(self, args: list[ParsedExpression]) -> FloorDiv:
        return FloorDiv(args[0], args[1])

    def mod(self, args: list[ParsedExpression]) -> Mod:
        return Mod(args[0], args[1])

    def cmp_chain(self, args: list[object]) -> ParsedExpression:
        # args alternates: sum_expr, CMP_OP token, sum_expr, CMP_OP token, sum_expr, ...
        # e.g.  [a, Token("CMP_OP","<"), b, Token("CMP_OP","<"), c]
        # → And(Lt(a, b), Lt(b, c))
        def _apply(op: str, left: ParsedExpression, right: ParsedExpression) -> ParsedExpression:
            if op == "==":
                return Eq(left, right)
            if op == "!=":
                return Ne(left, right)
            if op == "<":
                return Lt(left, right)
            if op == "<=":
                return Le(left, right)
            if op == ">":
                return Gt(left, right)
            if op == ">=":
                return Ge(left, right)
            raise ValueError(f"Unknown operator: {op!r}")  # pragma: no cover

        operands = [cast(ParsedExpression, args[i]) for i in range(0, len(args), 2)]
        operators = [str(args[i]) for i in range(1, len(args), 2)]
        pairs: list[ParsedExpression] = [
            _apply(op, operands[i], operands[i + 1])
            for i, op in enumerate(operators)
        ]
        result = pairs[0]
        for pair in pairs[1:]:
            result = And(result, pair)
        return result

    def and_(self, args: list[ParsedExpression]) -> And:
        return And(args[0], args[1])

    def or_(self, args: list[ParsedExpression]) -> Or:
        return Or(args[0], args[1])


_transformer = _ExprTransformer()


@functools.lru_cache(maxsize=1)
def _get_parser() -> Lark:
    return Lark(_GRAMMAR, parser="lalr", start="start")


def parse(text: str) -> ParsedExpression:
    """Parse an expression string into a ``ParsedExpression`` AST node.

    An empty or whitespace-only string is accepted and returns
    ``BooleanConstant(True)`` (the always-true, unconstrained case).

    The expression language supports:

    - Boolean literals: ``true``, ``false``
    - Integer literals: ``0``, ``1``, ``42``, ...
    - Root reference: ``self`` (equivalent to ``Reference(None, ())``)
    - Root reference with path: ``self[0]``, ``self[0][1]``
    - Named references: ``X``, ``Y``, ``MyLabel``
    - Named references with path: ``X[0]``, ``T[0][1]``
    - Anonymous (index) references: ``[0]``, ``[0][1]``
    - Arithmetic: ``+``, ``-``, ``*``, ``//``, ``%``
    - Unary negation: ``-X``, ``-42``
    - Comparison: ``==``, ``!=``, ``<``, ``<=``, ``>``, ``>=``
    - Boolean operators: ``and``, ``or``
    - Parentheses for grouping

    Operator precedence (lowest to highest):
        ``or`` < ``and`` < comparisons < ``+``/``-`` < ``*``/``//``/``%`` < unary ``-``

    Comparisons are associative (Python-style chaining): ``1 < x < 10`` is
    equivalent to ``1 < x and x < 10``.

    Reserved identifiers (not usable as label names in string expressions):
    ``true``, ``false``, ``and``, ``or``, ``self``.

    Examples::

        parse("")                          # BooleanConstant(True)  (empty = unconstrained)
        parse("true")                      # BooleanConstant(True)
        parse("self")                      # Reference(None, ())
        parse("self[0]")                   # Reference(None, (0,))
        parse("0 < self < 10")            # And(Lt(0, Reference(None,())), Lt(Reference(None,()), 10))
        parse("X >= 0 and X <= 9")         # And(Ge(ref("X"), ...), Le(ref("X"), ...))
        parse("1 < X < 10")               # And(Lt(IntegerConstant(1), X), Lt(X, IntegerConstant(10)))
        parse("[0] != [1]")               # Ne(Reference(None,(0,)), Reference(None,(1,)))
        parse("[0]*[0] + [1]*[1] == [2]*[2]")  # Pythagorean constraint

    Raises:
        lark.exceptions.LarkError: if the input is not a valid expression.
    """
    if not text.strip():
        return BooleanConstant(True)
    tree = _get_parser().parse(text)
    return cast(ParsedExpression, _transformer.transform(tree))
