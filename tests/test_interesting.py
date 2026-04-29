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
    LineIntervalsSet,
    Name,
    Regex,
    generate,
    parse,
)
from equivalib.core.expression import (
    And as _And,
    Expression,
    Ge as _Ge,
    IntegerConstant as _IC,
    Le as _Le,
    Reference as _Ref,
    reference,
)



class TicketCode(Regex):
    @staticmethod
    def expression() -> str:
        return r"(AB|CD)\d{2}"


def generate_pythagorean_triples(limit: int) -> set[tuple[int, int, int]]:
    tree = tuple[int, int, int]
    bounds = (
        f"[0] >= 1 and [0] <= {limit} and "
        f"[1] >= 1 and [1] <= {limit} and "
        f"[2] >= 1 and [2] <= {limit}"
    )
    ordered = "[0] <= [1] and [1] <= [2]"
    pythagorean = "[0] * [0] + [1] * [1] == [2] * [2]"
    return generate(tree, f"({bounds}) and ({ordered}) and ({pythagorean})")  # type: ignore[return-value]


def generate_sum_to_hundred_witness() -> set[tuple[int, ...]]:
    tree = cast(type[tuple[int, ...]], tuple[int, int, int, int, int, int, int, int, int, int])
    refs = [reference(i) for i in range(10)]

    bounded: And | None = None
    for ref in refs:
        per_ref = And(Ge(ref, IntegerConstant(0)), Le(ref, IntegerConstant(1)))
        bounded = per_ref if bounded is None else And(bounded, per_ref)

    sum_expr: Expression = refs[0]
    for ref in refs[1:]:
        sum_expr = Add(sum_expr, ref)

    assert bounded is not None
    constrained = And(bounded, Eq(sum_expr, IntegerConstant(5)))
    return generate(tree, constrained, {"[0]": "arbitrary", "[1]": "arbitrary", "[2]": "arbitrary", "[3]": "arbitrary", "[4]": "arbitrary", "[5]": "arbitrary", "[6]": "arbitrary", "[7]": "arbitrary", "[8]": "arbitrary", "[9]": "arbitrary"})


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


def test_interesting_tuple_constraint_with_string_ne():
    """String constraint: tuple elements must differ."""
    values = generate(tuple[bool, bool], "[0] != [1]")

    assert values == {(False, True), (True, False)}


def test_interesting_tuple_constraint_with_reference_paths():
    tree = cast(type[tuple[bool, bool]], Annotated[tuple[bool, bool], Name("B")])
    same_value = Eq(reference("B", 0), reference("B", 1))

    values = generate(tree, same_value, {"B": "all"})

    assert values == {(False, False), (True, True)}


def test_interesting_tuple_constraint_string_eq_on_named_tree():
    """String constraint with named label path syntax."""
    tree = cast(type[tuple[bool, bool]], Annotated[tuple[bool, bool], Name("B")])

    values = generate(tree, "B[0] == B[1]", {"B": "all"})

    assert values == {(False, False), (True, True)}


def test_interesting_ticket_code_regex_language():
    values = generate(TicketCode)

    assert len(values) == 200
    assert TicketCode("AB00") in values
    assert TicketCode("CD99") in values


def test_interesting_ticket_code_prefix_filtering_example():
    values = generate(TicketCode)
    ab_prefixed = {code for code in values if str(code.value).startswith("AB")}

    assert len(ab_prefixed) == 100
    assert TicketCode("AB42") in ab_prefixed
    assert TicketCode("CD42") not in ab_prefixed


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
    assert sum(only) == 5


def test_interesting_boolean_expression_true_is_unconstrained():
    values = generate(bool, BooleanExpression(True))

    assert values == {False, True}


def test_interesting_string_true_is_unconstrained():
    """String 'True' behaves identically to BooleanExpression(True)."""
    values = generate(bool, "True")

    assert values == {False, True}


def test_interesting_parse_returns_expression_ast():
    """parse() can be called standalone to inspect the resulting AST."""
    expr = parse("X >= 0 and X <= 9")
    assert expr == _And(_Ge(_Ref("X", ()), _IC(0)), _Le(_Ref("X", ()), _IC(9)))


class PairsUpTo5(LineIntervalsSet):
    @classmethod
    def number_of_intervals(cls) -> int:
        return 2

    @classmethod
    def range_minimum(cls) -> int:
        return 0

    @classmethod
    def range_maximum(cls) -> int:
        return 5


def test_interesting_line_intervals_set_two_intervals_four_classes():
    """Generating PairsUpTo5 yields one representative per equivalence class.

    Two integer intervals can relate in exactly four ways:
    touch (one interval ends exactly where the other begins),
    kiss (endpoints are adjacent, differing by exactly 1),
    overlap (intervals share a non-degenerate interior),
    or disjoint — so there are exactly 4 representatives.
    """
    representatives = generate(PairsUpTo5)

    assert len(representatives) == 4
    for rep in representatives:
        start_a, end_a = rep.intervals[0]
        start_b, end_b = rep.intervals[1]
        assert start_a <= end_a
        assert start_b <= end_b
        assert 0 <= start_a and end_a <= 5
        assert 0 <= start_b and end_b <= 5
