from __future__ import annotations

from typing import Iterator

from equivalib.core import BooleanExpression, Extension, Regex, generate
from equivalib.core.expression import Expression


class TicketCode(Regex):
    @staticmethod
    def expression() -> str:
        return r"(AB|CD)\d{2}"


class PythagoreanTriple(Extension):
    def __init__(self, value: tuple[int, int, int]):
        self.value = value

    def __hash__(self) -> int:
        return hash(self.value)

    def __eq__(self, other: object) -> bool:
        return isinstance(other, PythagoreanTriple) and self.value == other.value

    @staticmethod
    def initialize(tree: object, constraint: Expression) -> None:
        del tree, constraint

    @staticmethod
    def enumerate_all(tree: object, constraint: Expression, address: str | None) -> Iterator[PythagoreanTriple]:
        del tree, constraint, address
        limit = 30
        for a in range(1, limit + 1):
            for b in range(a, limit + 1):
                for c in range(b, limit + 1):
                    if (a * a) + (b * b) == (c * c):
                        yield PythagoreanTriple((a, b, c))

    @staticmethod
    def arbitrary(tree: object, constraint: Expression, address: str | None) -> PythagoreanTriple | None:
        del tree, constraint, address
        return PythagoreanTriple((3, 4, 5))

    @staticmethod
    def uniform_random(tree: object, constraint: Expression, address: str | None) -> PythagoreanTriple | None:
        del tree, constraint, address
        return PythagoreanTriple((8, 15, 17))


def test_interesting_single_boolean_value_generation():
    values = generate(bool)

    assert values == {False, True}


def test_interesting_tuple_of_booleans_generation():
    values = generate(tuple[bool, bool])

    assert values == {(False, False), (False, True), (True, False), (True, True)}


def test_interesting_ticket_code_regex_language():
    values = generate(TicketCode)

    assert len(values) == 200
    assert TicketCode("AB00") in values
    assert TicketCode("CD99") in values


def test_interesting_pythagorean_triples_extension_generation():
    triples = generate(PythagoreanTriple, BooleanExpression(True))

    unpacked = {item.value for item in triples}
    assert (3, 4, 5) in unpacked
    assert (5, 12, 13) in unpacked
    assert (20, 21, 29) in unpacked
    assert all((a * a) + (b * b) == (c * c) for a, b, c in unpacked)
