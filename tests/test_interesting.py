from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated, Tuple

from equivalib import Super, ValueRange, generate_instances
from equivalib.core import Regex, generate


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
    tree = Tuple[tuple(Annotated[bool, Super] for _ in range(20))]

    values = set(generate_instances(tree))

    assert len(values) == 1
    only = next(iter(values))
    assert isinstance(only, tuple)
    assert len(only) == 20
    assert set(only).issubset({False, True})


@dataclass(frozen=True)
class SumToHundred:
    x0: Annotated[int, ValueRange(0, 999), Super]
    x1: Annotated[int, ValueRange(0, 999), Super]
    x2: Annotated[int, ValueRange(0, 999), Super]
    x3: Annotated[int, ValueRange(0, 999), Super]
    x4: Annotated[int, ValueRange(0, 999), Super]
    x5: Annotated[int, ValueRange(0, 999), Super]
    x6: Annotated[int, ValueRange(0, 999), Super]
    x7: Annotated[int, ValueRange(0, 999), Super]
    x8: Annotated[int, ValueRange(0, 999), Super]
    x9: Annotated[int, ValueRange(0, 999), Super]

    def __post_init__(self):
        assert self.x0 + self.x1 + self.x2 + self.x3 + self.x4 + self.x5 + self.x6 + self.x7 + self.x8 + self.x9 == 100


def test_interesting_sat_constrained_large_domain_finds_a_witness():
    values = set(generate_instances(SumToHundred))

    assert len(values) == 1
    item = next(iter(values))
    assert sum((item.x0, item.x1, item.x2, item.x3, item.x4, item.x5, item.x6, item.x7, item.x8, item.x9)) == 100
