from __future__ import annotations

from functools import reduce
from typing import Annotated, Iterable, Tuple

from equivalib.core import (
    Add,
    And,
    BooleanExpression,
    Eq,
    Ge,
    IntegerConstant,
    Le,
    Name,
    Reference,
    Regex,
    generate,
)


def _and_all(expressions: Iterable[object]) -> object:
    exprs = list(expressions)
    assert exprs
    return reduce(And, exprs)


class HexPairWithDigit(Regex):
    @staticmethod
    def expression() -> str:
        return r"[A-F]{2}\d"


def test_interesting_regex_finite_language_is_enumerated():
    values = generate(HexPairWithDigit)

    assert len(values) == 6 * 6 * 10
    assert HexPairWithDigit("AA0") in values
    assert HexPairWithDigit("FF9") in values


def test_interesting_huge_boolean_tree_collapses_to_one_arbitrary_witness():
    tree = Annotated[Tuple[tuple(bool for _ in range(20))], Name("Bits")]

    values = generate(
        tree,
        BooleanExpression(True),
        {"Bits": "arbitrary"},
    )

    assert values == {tuple(False for _ in range(20))}


def test_interesting_sat_constrained_large_domain_picks_canonical_solution():
    tree = Annotated[Tuple[tuple(int for _ in range(10))], Name("X")]
    refs = [Reference("X", (i,)) for i in range(10)]

    bounds = _and_all(
        And(Ge(ref, IntegerConstant(0)), Le(ref, IntegerConstant(999)))
        for ref in refs
    )
    sum_eq_100 = Eq(reduce(Add, refs), IntegerConstant(100))

    values = generate(
        tree,
        And(bounds, sum_eq_100),
        {"X": "arbitrary"},
    )

    assert values == {(0, 0, 0, 0, 0, 0, 0, 0, 0, 100)}
