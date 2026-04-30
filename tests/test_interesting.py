from __future__ import annotations

from typing import Annotated, Mapping, cast

from equivalib.core import (
    Name,
    Regex,
    generate,
    intervals,
)
from equivalib.core.methods import Method


class TicketCode(Regex):
    @staticmethod
    def expression() -> str:
        return r"(AB|CD)\d{2}"


def generate_pythagorean_triples(limit: int) -> set[tuple[int, int, int]]:
    tree: type[tuple[int, int, int]] = tuple[int, int, int]
    bounds = (
        f"1 <= [0] and [0] <= {limit} and "
        f"1 <= [1] and [1] <= {limit} and "
        f"1 <= [2] and [2] <= {limit}"
    )
    ordered = "[0] <= [1] and [1] <= [2]"
    pythagorean = "[0]*[0] + [1]*[1] == [2]*[2]"
    constraint = f"{bounds} and {ordered} and {pythagorean}"
    return generate(tree, constraint)


def generate_sum_to_hundred_witness() -> set[tuple[int, ...]]:
    tree = cast(type[tuple[int, ...]], tuple[int, int, int, int, int, int, int, int, int, int])
    bounds = " and ".join(f"0 <= [{i}] and [{i}] <= 1" for i in range(10))
    total = " + ".join(f"[{i}]" for i in range(10))
    constraint = f"{bounds} and {total} == 5"
    methods: Mapping[str, Method] = {f"[{i}]": "arbitrary" for i in range(10)}
    return generate(tree, constraint, methods)


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


def test_interesting_tuple_constraint_with_reference_paths():
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
    values = generate(bool, "true")

    assert values == {False, True}


PairsUpTo5 = intervals(on=(0, 5), n=2)


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

