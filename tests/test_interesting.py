from __future__ import annotations

from typing import Annotated, cast

from equivalib.core import (
    Add,
    And,
    BooleanExpression,
    Eq,
    Ge,
    IntegerConstant,
    Le,
    Mul,
    Name,
    Reference,
    Regex,
    generate,
)
from equivalib.core.expression import Expression



class TicketCode(Regex):
    @staticmethod
    def expression() -> str:
        return r"(AB|CD)\d{2}"


def generate_pythagorean_triples(limit: int) -> set[tuple[int, int, int]]:
    tree = cast(type[tuple[int, int, int]], Annotated[tuple[int, int, int], Name("T")])
    a = Reference("T", (0,))
    b = Reference("T", (1,))
    c = Reference("T", (2,))

    bounds = And(
        And(Ge(a, IntegerConstant(1)), Le(a, IntegerConstant(limit))),
        And(
            And(Ge(b, IntegerConstant(1)), Le(b, IntegerConstant(limit))),
            And(Ge(c, IntegerConstant(1)), Le(c, IntegerConstant(limit))),
        ),
    )
    ordered = And(Le(a, b), Le(b, c))
    pythagorean = Eq(Add(Mul(a, a), Mul(b, b)), Mul(c, c))

    return generate(tree, And(bounds, And(ordered, pythagorean)), {"T": "all"})


def generate_sum_to_hundred_witness() -> set[tuple[int, ...]]:
    tree = cast(
        type[tuple[int, ...]],
        Annotated[tuple[int, int, int, int, int, int, int, int, int, int], Name("X")],
    )
    refs = [Reference("X", (i,)) for i in range(10)]

    bounded: And | None = None
    for ref in refs:
        per_ref = And(Ge(ref, IntegerConstant(0)), Le(ref, IntegerConstant(999)))
        bounded = per_ref if bounded is None else And(bounded, per_ref)

    sum_expr: Expression = refs[0]
    for ref in refs[1:]:
        sum_expr = Add(sum_expr, ref)

    assert bounded is not None
    constrained = And(bounded, Eq(sum_expr, IntegerConstant(100)))
    return generate(tree, constrained, {"X": "arbitrary"})


def test_interesting_single_boolean_value_generation():
    values = generate(bool)

    assert values == {False, True}


def test_interesting_tuple_of_booleans_generation():
    values = generate(tuple[bool, bool])

    assert values == {(False, False), (False, True), (True, False), (True, True)}


def test_interesting_direct_indexing_on_generated_tuple_values():
    values = generate(tuple[bool, bool])
    only_true_first = {item for item in values if item[0]}

    assert only_true_first == {(True, False), (True, True)}


def test_interesting_ticket_code_regex_language():
    values = generate(TicketCode)

    assert len(values) == 200
    assert TicketCode("AB00") in values
    assert TicketCode("CD99") in values


def test_interesting_pythagorean_triples_are_found_via_sat_constraints():
    triples = generate_pythagorean_triples(limit=30)

    assert (3, 4, 5) in triples
    assert (5, 12, 13) in triples
    assert (20, 21, 29) in triples
    assert all((a * a) + (b * b) == (c * c) for a, b, c in triples)


def test_interesting_large_integer_domain_can_return_one_arbitrary_witness():
    values = generate_sum_to_hundred_witness()

    assert len(values) == 1
    only = next(iter(values))
    assert sum(only) == 100


def test_interesting_boolean_expression_true_is_unconstrained():
    values = generate(bool, BooleanExpression(True))

    assert values == {False, True}
