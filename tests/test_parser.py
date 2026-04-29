"""Tests for the expression string parser (equivalib.core.parser)."""

from __future__ import annotations

import pytest
from lark.exceptions import LarkError

from equivalib.core import generate
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
    Reference,
    Sub,
)
from equivalib.core.parser import parse


# ---------------------------------------------------------------------------
# Boolean literals
# ---------------------------------------------------------------------------

def test_parse_true():
    assert parse("true") == BooleanConstant(True)


def test_parse_false():
    assert parse("false") == BooleanConstant(False)


# ---------------------------------------------------------------------------
# Integer literals
# ---------------------------------------------------------------------------

def test_parse_zero():
    assert parse("0") == IntegerConstant(0)


def test_parse_positive_integer():
    assert parse("42") == IntegerConstant(42)


def test_parse_large_integer():
    assert parse("1000000") == IntegerConstant(1000000)


# ---------------------------------------------------------------------------
# References
# ---------------------------------------------------------------------------

def test_parse_labeled_reference_bare():
    assert parse("X") == Reference("X", ())


def test_parse_labeled_reference_single_index():
    assert parse("X[0]") == Reference("X", (0,))


def test_parse_labeled_reference_multi_index():
    assert parse("T[0][1]") == Reference("T", (0, 1))


def test_parse_anonymous_reference_single():
    assert parse("[0]") == Reference(None, (0,))


def test_parse_anonymous_reference_multi():
    assert parse("[0][1]") == Reference(None, (0, 1))


def test_parse_labeled_reference_underscore():
    assert parse("my_label") == Reference("my_label", ())


def test_parse_labeled_reference_mixed_case():
    assert parse("MyLabel") == Reference("MyLabel", ())


# ---------------------------------------------------------------------------
# 'self' root-reference identifier
# ---------------------------------------------------------------------------

def test_parse_self_bare():
    """'self' alone parses to Reference(None, ()) — the anonymous root reference."""
    assert parse("self") == Reference(None, ())


def test_parse_self_with_single_index():
    """'self[0]' parses to Reference(None, (0,))."""
    assert parse("self[0]") == Reference(None, (0,))


def test_parse_self_with_multiple_indices():
    """'self[0][1]' parses to Reference(None, (0, 1))."""
    assert parse("self[0][1]") == Reference(None, (0, 1))


def test_parse_self_in_comparison_chain():
    """'0 < self < 10' parses identically to using [0] on a root int."""
    self_ref = Reference(None, ())
    expected = And(Lt(IntegerConstant(0), self_ref), Lt(self_ref, IntegerConstant(10)))
    assert parse("0 < self < 10") == expected


def test_parse_self_indexed_same_as_anonymous_ref():
    """'self[0]' produces the same AST as '[0]'."""
    assert parse("self[0]") == parse("[0]")
    assert parse("self[0][1]") == parse("[0][1]")


# ---------------------------------------------------------------------------
# Unary negation
# ---------------------------------------------------------------------------

def test_parse_neg_integer():
    assert parse("-42") == Neg(IntegerConstant(42))


def test_parse_neg_reference():
    assert parse("-X") == Neg(Reference("X", ()))


def test_parse_double_neg():
    assert parse("--X") == Neg(Neg(Reference("X", ())))


# ---------------------------------------------------------------------------
# Arithmetic
# ---------------------------------------------------------------------------

def test_parse_add():
    assert parse("X + Y") == Add(Reference("X", ()), Reference("Y", ()))


def test_parse_sub():
    assert parse("X - Y") == Sub(Reference("X", ()), Reference("Y", ()))


def test_parse_mul():
    assert parse("X * Y") == Mul(Reference("X", ()), Reference("Y", ()))


def test_parse_floordiv():
    assert parse("X // Y") == FloorDiv(Reference("X", ()), Reference("Y", ()))


def test_parse_mod():
    assert parse("X % Y") == Mod(Reference("X", ()), Reference("Y", ()))


def test_parse_arithmetic_left_associativity():
    # X + Y + Z => Add(Add(X, Y), Z)
    result = parse("X + Y + Z")
    expected = Add(Add(Reference("X", ()), Reference("Y", ())), Reference("Z", ()))
    assert result == expected


def test_parse_mul_binds_tighter_than_add():
    # X + Y * Z => Add(X, Mul(Y, Z))
    result = parse("X + Y * Z")
    expected = Add(Reference("X", ()), Mul(Reference("Y", ()), Reference("Z", ())))
    assert result == expected


# ---------------------------------------------------------------------------
# Comparison
# ---------------------------------------------------------------------------

def test_parse_eq():
    assert parse("X == Y") == Eq(Reference("X", ()), Reference("Y", ()))


def test_parse_ne():
    assert parse("X != Y") == Ne(Reference("X", ()), Reference("Y", ()))


def test_parse_lt():
    assert parse("X < Y") == Lt(Reference("X", ()), Reference("Y", ()))


def test_parse_le():
    assert parse("X <= Y") == Le(Reference("X", ()), Reference("Y", ()))


def test_parse_gt():
    assert parse("X > Y") == Gt(Reference("X", ()), Reference("Y", ()))


def test_parse_ge():
    assert parse("X >= Y") == Ge(Reference("X", ()), Reference("Y", ()))


def test_parse_comparison_with_constants():
    assert parse("X >= 0") == Ge(Reference("X", ()), IntegerConstant(0))
    assert parse("X <= 9") == Le(Reference("X", ()), IntegerConstant(9))


# ---------------------------------------------------------------------------
# Boolean operators
# ---------------------------------------------------------------------------

def test_parse_and():
    result = parse("X and Y")
    assert result == And(Reference("X", ()), Reference("Y", ()))


def test_parse_or():
    result = parse("X or Y")
    assert result == Or(Reference("X", ()), Reference("Y", ()))


def test_parse_and_binds_tighter_than_or():
    # X or Y and Z => Or(X, And(Y, Z))
    result = parse("X or Y and Z")
    expected = Or(Reference("X", ()), And(Reference("Y", ()), Reference("Z", ())))
    assert result == expected


def test_parse_and_chains():
    result = parse("X >= 0 and X <= 9")
    expected = And(
        Ge(Reference("X", ()), IntegerConstant(0)),
        Le(Reference("X", ()), IntegerConstant(9)),
    )
    assert result == expected


# ---------------------------------------------------------------------------
# Parentheses
# ---------------------------------------------------------------------------

def test_parse_parenthesized_expression():
    result = parse("(X + Y) * Z")
    expected = Mul(Add(Reference("X", ()), Reference("Y", ())), Reference("Z", ()))
    assert result == expected


def test_parse_nested_parentheses():
    result = parse("((X))")
    assert result == Reference("X", ())


def test_parse_parentheses_override_precedence():
    # (X + Y) * Z  vs  X + Y * Z
    with_parens = parse("(X + Y) * Z")
    without_parens = parse("X + Y * Z")
    assert with_parens != without_parens


# ---------------------------------------------------------------------------
# Whitespace
# ---------------------------------------------------------------------------

def test_parse_ignores_extra_whitespace():
    assert parse("  X  >=  0  ") == Ge(Reference("X", ()), IntegerConstant(0))


def test_parse_no_spaces_around_operators():
    assert parse("X>=0") == Ge(Reference("X", ()), IntegerConstant(0))


# ---------------------------------------------------------------------------
# Complex expressions (as used in practice)
# ---------------------------------------------------------------------------

def test_parse_pythagorean_constraint():
    result = parse("[0]*[0] + [1]*[1] == [2]*[2]")
    a, b, c = Reference(None, (0,)), Reference(None, (1,)), Reference(None, (2,))
    expected = Eq(
        Add(Mul(a, a), Mul(b, b)),
        Mul(c, c),
    )
    assert result == expected


def test_parse_range_constraint():
    result = parse("X >= 1 and X <= 10")
    expected = And(
        Ge(Reference("X", ()), IntegerConstant(1)),
        Le(Reference("X", ()), IntegerConstant(10)),
    )
    assert result == expected


def test_parse_ne_on_anonymous_references():
    result = parse("[0] != [1]")
    expected = Ne(Reference(None, (0,)), Reference(None, (1,)))
    assert result == expected


def test_parse_complex_named_constraint():
    result = parse("X >= 0 and X <= 9 and Y >= 0 and Y <= 9 and X > Y")
    x = Reference("X", ())
    y = Reference("Y", ())
    zero = IntegerConstant(0)
    nine = IntegerConstant(9)
    expected = And(
        And(
            And(
                And(Ge(x, zero), Le(x, nine)),
                Ge(y, zero),
            ),
            Le(y, nine),
        ),
        Gt(x, y),
    )
    assert result == expected


def test_parse_floordiv_and_mod():
    result = parse("X // 2 == Y % 3")
    x = Reference("X", ())
    y = Reference("Y", ())
    two = IntegerConstant(2)
    three = IntegerConstant(3)
    expected = Eq(FloorDiv(x, two), Mod(y, three))
    assert result == expected


# ---------------------------------------------------------------------------
# Error cases
# ---------------------------------------------------------------------------

def test_parse_empty_string_returns_true():
    """An empty string is accepted and returns BooleanConstant(True)."""
    assert parse("") == BooleanConstant(True)


def test_parse_whitespace_only_returns_true():
    """A whitespace-only string is accepted and returns BooleanConstant(True)."""
    assert parse("   ") == BooleanConstant(True)


def test_parse_invalid_syntax_raises():
    with pytest.raises(LarkError):
        parse("X ++ Y")


def test_parse_unclosed_paren_raises():
    with pytest.raises(LarkError):
        parse("(X + Y")


def test_parse_bare_operator_raises():
    with pytest.raises(LarkError):
        parse("+ X")


def test_parse_chained_comparison_two_ops():
    """Chained comparisons like '1 < x < 10' parse as And(Lt(1,x), Lt(x,10))."""
    result = parse("1 < X < 10")
    x = Reference("X", ())
    expected = And(Lt(IntegerConstant(1), x), Lt(x, IntegerConstant(10)))
    assert result == expected


def test_parse_chained_comparison_three_ops():
    """Three-way chained comparison 'a < b < c < d'."""
    result = parse("1 < X < 10 < 100")
    x = Reference("X", ())
    expected = And(
        And(Lt(IntegerConstant(1), x), Lt(x, IntegerConstant(10))),
        Lt(IntegerConstant(10), IntegerConstant(100)),
    )
    assert result == expected


def test_parse_chained_comparison_with_and_works():
    """Explicit 'and' to combine comparisons still works."""
    result = parse("1 < X and X < 10")
    x = Reference("X", ())
    expected = And(Lt(IntegerConstant(1), x), Lt(x, IntegerConstant(10)))
    assert result == expected


# ---------------------------------------------------------------------------
# Integration: parse() result works with generate()
# ---------------------------------------------------------------------------

def test_parse_result_usable_in_generate():
    result = generate(tuple[bool, bool], parse("[0] != [1]"))
    assert result == {(False, True), (True, False)}


def test_parse_string_directly_in_generate():
    result = generate(tuple[bool, bool], "[0] != [1]")
    assert result == {(False, True), (True, False)}


def test_generate_string_and_parsed_give_same_result():
    constraint_str = "[0] != [1]"
    constraint_ast = parse(constraint_str)

    result_str = generate(tuple[bool, bool], constraint_str)
    result_ast = generate(tuple[bool, bool], constraint_ast)

    assert result_str == result_ast
