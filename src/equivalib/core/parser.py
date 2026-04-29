"""BNF-based expression parser for the new core.

Parses string expressions into ``ParsedExpression`` AST nodes.

Grammar (EBNF-style, maps 1-to-1 to the lark BNF grammar below):

    expr        = or_expr
    or_expr     = and_expr ("or" and_expr)*
    and_expr    = cmp_expr ("and" cmp_expr)*
    cmp_expr    = sum_expr (cmp_op sum_expr)?
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

Keywords reserved by the grammar: ``true``, ``false``, ``and``, ``or``.
Label identifiers that spell a reserved keyword are not supported in string
expressions; use the ``ParsedExpression`` AST constructors directly instead.
"""

from __future__ import annotations

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
             | cmp_expr "==" sum_expr  -> eq
             | cmp_expr "!=" sum_expr  -> ne
             | cmp_expr "<" sum_expr   -> lt
             | cmp_expr "<=" sum_expr  -> le
             | cmp_expr ">" sum_expr   -> gt
             | cmp_expr ">=" sum_expr  -> ge

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

    def eq(self, args: list[ParsedExpression]) -> Eq:
        return Eq(args[0], args[1])

    def ne(self, args: list[ParsedExpression]) -> Ne:
        return Ne(args[0], args[1])

    def lt(self, args: list[ParsedExpression]) -> Lt:
        return Lt(args[0], args[1])

    def le(self, args: list[ParsedExpression]) -> Le:
        return Le(args[0], args[1])

    def gt(self, args: list[ParsedExpression]) -> Gt:
        return Gt(args[0], args[1])

    def ge(self, args: list[ParsedExpression]) -> Ge:
        return Ge(args[0], args[1])

    def and_(self, args: list[ParsedExpression]) -> And:
        return And(args[0], args[1])

    def or_(self, args: list[ParsedExpression]) -> Or:
        return Or(args[0], args[1])


_parser = Lark(_GRAMMAR, parser="lalr", start="start")
_transformer = _ExprTransformer()


def parse(text: str) -> ParsedExpression:
    """Parse an expression string into a ``ParsedExpression`` AST node.

    The expression language supports:

    - Boolean literals: ``true``, ``false``
    - Integer literals: ``0``, ``1``, ``42``, ...
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

    Examples::

        parse("true")                      # BooleanConstant(True)
        parse("X >= 0 and X <= 9")         # And(Ge(ref("X"), ...), Le(ref("X"), ...))
        parse("[0] != [1]")               # Ne(Reference(None,(0,)), Reference(None,(1,)))
        parse("[0]*[0] + [1]*[1] == [2]*[2]")  # Pythagorean constraint

    Raises:
        lark.exceptions.LarkError: if the input is not a valid expression.
    """
    tree = _parser.parse(text)
    return _transformer.transform(tree)
