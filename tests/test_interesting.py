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


def _sum_refs(labels: list[str]) -> object:
    refs = [Reference(label) for label in labels]
    assert refs
    return reduce(Add, refs)


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
    labels = [f"B{i:02d}" for i in range(20)]
    bool_leaves = tuple(Annotated[bool, Name(label)] for label in labels)
    tree = Tuple[bool_leaves]

    values = generate(
        tree,
        BooleanExpression(True),
        {label: "arbitrary" for label in labels},
    )

    assert values == {tuple(False for _ in labels)}


def test_interesting_sat_constrained_large_domain_picks_canonical_solution():
    labels = [f"X{i}" for i in range(10)]
    int_leaves = tuple(Annotated[int, Name(label)] for label in labels)
    tree = Tuple[int_leaves]

    bounds = _and_all(
        And(Ge(Reference(label), IntegerConstant(0)), Le(Reference(label), IntegerConstant(999)))
        for label in labels
    )
    sum_eq_100 = Eq(_sum_refs(labels), IntegerConstant(100))

    values = generate(
        tree,
        And(bounds, sum_eq_100),
        {label: "arbitrary" for label in labels},
    )

    assert values == {(0, 0, 0, 0, 0, 0, 0, 0, 0, 100)}
