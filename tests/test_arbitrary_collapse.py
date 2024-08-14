
# pylint: disable=duplicate-code
# pylint: disable=unused-import

from dataclasses import dataclass
from typing import Literal, Union
import os
import random
import pytest

import equivalib.all as equivalib
from equivalib.all import BoundedInt, supervalue


# Define the fixture to fix the random seed
@pytest.fixture(scope='function', autouse=True)
def fixed_random_seed():
    random.seed(42)
    yield
    random.seed()


@dataclass
class SuperEntangled:
    a: bool = supervalue()
    b: bool = supervalue()

    def __post_init__(self):
        assert self.a != self.b


def test_super_entangled():
    theories = equivalib.generate_sentences([SuperEntangled])

    assert len(theories) == 1

    sentence = equivalib.arbitrary_collapse(theories[0])
    assert sentence.assignments \
        in [{'a': True, 'b': False, 'c': SuperEntangled(True, False)},
            {'a': False, 'b': True, 'c': SuperEntangled(False, True)}]

    assert str(sentence) \
        in ('a = True; b = False; c = SuperEntangled(a, b);',
            'a = False; b = True; c = SuperEntangled(a, b);')



@dataclass(frozen=True)
class Interval:
    x: BoundedInt[Literal[1], Literal[9]] = supervalue()
    y: BoundedInt[Literal[1], Literal[9]] = supervalue()

    def __post_init__(self):
        assert self.y > self.x


def test_interval():
    theories = equivalib.generate_sentences([Interval])
    assert len(theories) == 1
    sentence = equivalib.arbitrary_collapse(theories[0])
    assert str(sentence) \
        == 'a = 1; b = 2; c = Interval(a, b);'


@dataclass
class Overlap:
    a: Interval
    b: Interval

    def __post_init__(self):
        assert self.b.x <= self.a.y
        assert self.b.y >= self.a.y


def test_1_overlaping_interval():
    theories = equivalib.generate_sentences([Interval, Overlap])
    assert len(theories) == 1
    sentence = equivalib.arbitrary_collapse(theories[0])
    assert str(sentence) \
        == 'a = 1; b = 9; c = Interval(a, b); d = Overlap(c, c);'



@dataclass(frozen=True)
class Interval2:
    name: Union[Literal["A"], Literal["B"]]
    x: BoundedInt[Literal[1], Literal[9]] = supervalue()
    y: BoundedInt[Literal[1], Literal[9]] = supervalue()

    def __post_init__(self):
        assert self.y > self.x


@dataclass(frozen=True)
class Overlap2:
    a: Interval2
    b: Interval2

    def __post_init__(self):
        assert self.b.x <= self.a.y
        assert self.b.y >= self.a.y


def test_2_overlaping_intervals():
    theories = equivalib.generate_sentences([Interval2, Overlap2])
    assert len(theories) == 2
    strings = list(map(str, map(equivalib.arbitrary_collapse, theories)))

    dedup = list(set(strings))
    assert len(dedup) == len(strings)
    assert sorted(dedup) == sorted(strings)

    assert strings \
        == ["a = 1; b = 9; c = Interval2('A', a, b); d = Overlap2(c, c);",
            "a = 1; b = 9; c = Interval2('B', a, b); d = Overlap2(c, c);"]


@dataclass(frozen=True)
class Interval3:
    name: Union[Literal["A"], Literal["B"], Literal["C"]]
    x: BoundedInt[Literal[1], Literal[9]] = supervalue()
    y: BoundedInt[Literal[1], Literal[9]] = supervalue()

    def __post_init__(self):
        assert self.y > self.x


@dataclass(frozen=True)
class Overlap3:
    a: Interval3
    b: Interval3

    def __post_init__(self):
        assert self.b.x < self.a.y
        assert self.b.y > self.a.y


# @pytest.mark.skipif(not os.getenv('CI'), reason="This test takes too long, it is for CI only")
# def test_3_overlaping_intervals():
#     theories = equivalib.generate_sentences([Interval3, Overlap3])
#     assert len(theories) == 30
#     strings = list(map(str, map(equivalib.arbitrary_collapse, theories)))

#     dedup = list(set(strings))
#     assert len(dedup) == len(strings)
#     assert sorted(dedup) == sorted(strings)

#     assert strings \
#         == ["a = 1; b = 2; c = Interval3('A', a, b); d = 1; e = 9; f = Interval3('B', d, e); g = Overlap3(c, f);",
#             "a = 1; b = 9; c = Interval3('A', a, b); d = 1; e = 2; f = Interval3('B', d, e); g = Overlap3(f, c);",
#             "a = 1; b = 2; c = Interval3('A', a, b); d = 1; e = 9; f = Interval3('C', d, e); g = Overlap3(c, f);",
#             "a = 1; b = 9; c = Interval3('A', a, b); d = 1; e = 2; f = Interval3('C', d, e); g = Overlap3(f, c);",
#             "a = 1; b = 2; c = Interval3('B', a, b); d = 1; e = 9; f = Interval3('C', d, e); g = Overlap3(c, f);",
#             "a = 1; b = 9; c = Interval3('B', a, b); d = 1; e = 2; f = Interval3('C', d, e); g = Overlap3(f, c);",
#             "a = 1; b = 2; c = Interval3('A', a, b); d = 1; e = 9; f = Interval3('B', d, e); g = 1; h = 2; i = Interval3('C', g, h); j = Overlap3(c, f);",
#             "a = 1; b = 2; c = Interval3('A', a, b); d = 1; e = 2; f = Interval3('B', d, e); g = 1; h = 9; i = Interval3('C', g, h); j = Overlap3(c, i);",
#             "a = 1; b = 2; c = Interval3('A', a, b); d = 1; e = 9; f = Interval3('B', d, e); g = 1; h = 9; i = Interval3('C', g, h); j = Overlap3(c, f); k = Overlap3(c, i);",
#             "a = 1; b = 9; c = Interval3('A', a, b); d = 1; e = 2; f = Interval3('B', d, e); g = 1; h = 2; i = Interval3('C', g, h); j = Overlap3(f, c);",
#             "a = 1; b = 3; c = Interval3('A', a, b); d = 1; e = 2; f = Interval3('B', d, e); g = 1; h = 9; i = Interval3('C', g, h); j = Overlap3(c, i); k = Overlap3(f, c);",
#             "a = 1; b = 2; c = Interval3('A', a, b); d = 1; e = 2; f = Interval3('B', d, e); g = 1; h = 9; i = Interval3('C', g, h); j = Overlap3(f, i);",
#             "a = 1; b = 2; c = Interval3('A', a, b); d = 1; e = 3; f = Interval3('B', d, e); g = 1; h = 9; i = Interval3('C', g, h); j = Overlap3(c, f); k = Overlap3(f, i);",
#             "a = 1; b = 2; c = Interval3('A', a, b); d = 1; e = 2; f = Interval3('B', d, e); g = 1; h = 9; i = Interval3('C', g, h); j = Overlap3(c, i); k = Overlap3(f, i);",
#             "a = 1; b = 2; c = Interval3('A', a, b); d = 1; e = 3; f = Interval3('B', d, e); g = 1; h = 9; i = Interval3('C', g, h); j = Overlap3(c, f); k = Overlap3(c, i); l = Overlap3(f, i);",
#             "a = 1; b = 9; c = Interval3('A', a, b); d = 1; e = 2; f = Interval3('B', d, e); g = 1; h = 9; i = Interval3('C', g, h); j = Overlap3(f, c); k = Overlap3(f, i);",
#             "a = 1; b = 3; c = Interval3('A', a, b); d = 1; e = 2; f = Interval3('B', d, e); g = 1; h = 9; i = Interval3('C', g, h); j = Overlap3(c, i); k = Overlap3(f, c); l = Overlap3(f, i);",
#             "a = 1; b = 9; c = Interval3('A', a, b); d = 1; e = 2; f = Interval3('B', d, e); g = 1; h = 2; i = Interval3('C', g, h); j = Overlap3(i, c);",
#             "a = 1; b = 3; c = Interval3('A', a, b); d = 1; e = 9; f = Interval3('B', d, e); g = 1; h = 2; i = Interval3('C', g, h); j = Overlap3(c, f); k = Overlap3(i, c);",
#             "a = 1; b = 9; c = Interval3('A', a, b); d = 1; e = 2; f = Interval3('B', d, e); g = 1; h = 2; i = Interval3('C', g, h); j = Overlap3(f, c); k = Overlap3(i, c);",
#             "a = 1; b = 9; c = Interval3('A', a, b); d = 1; e = 2; f = Interval3('B', d, e); g = 1; h = 3; i = Interval3('C', g, h); j = Overlap3(f, i); k = Overlap3(i, c);",
#             "a = 1; b = 9; c = Interval3('A', a, b); d = 1; e = 2; f = Interval3('B', d, e); g = 1; h = 3; i = Interval3('C', g, h); j = Overlap3(f, c); k = Overlap3(f, i); l = Overlap3(i, c);",
#             "a = 1; b = 2; c = Interval3('A', a, b); d = 1; e = 9; f = Interval3('B', d, e); g = 1; h = 2; i = Interval3('C', g, h); j = Overlap3(i, f);",
#             "a = 1; b = 2; c = Interval3('A', a, b); d = 1; e = 9; f = Interval3('B', d, e); g = 1; h = 2; i = Interval3('C', g, h); j = Overlap3(c, f); k = Overlap3(i, f);",
#             "a = 1; b = 2; c = Interval3('A', a, b); d = 1; e = 9; f = Interval3('B', d, e); g = 1; h = 3; i = Interval3('C', g, h); j = Overlap3(c, i); k = Overlap3(i, f);",
#             "a = 1; b = 2; c = Interval3('A', a, b); d = 1; e = 9; f = Interval3('B', d, e); g = 1; h = 3; i = Interval3('C', g, h); j = Overlap3(c, f); k = Overlap3(c, i); l = Overlap3(i, f);",
#             "a = 1; b = 9; c = Interval3('A', a, b); d = 1; e = 3; f = Interval3('B', d, e); g = 1; h = 2; i = Interval3('C', g, h); j = Overlap3(f, c); k = Overlap3(i, f);",
#             "a = 1; b = 9; c = Interval3('A', a, b); d = 1; e = 9; f = Interval3('B', d, e); g = 1; h = 2; i = Interval3('C', g, h); j = Overlap3(i, c); k = Overlap3(i, f);",
#             "a = 1; b = 3; c = Interval3('A', a, b); d = 1; e = 9; f = Interval3('B', d, e); g = 1; h = 2; i = Interval3('C', g, h); j = Overlap3(c, f); k = Overlap3(i, c); l = Overlap3(i, f);",
#             "a = 1; b = 9; c = Interval3('A', a, b); d = 1; e = 3; f = Interval3('B', d, e); g = 1; h = 2; i = Interval3('C', g, h); j = Overlap3(f, c); k = Overlap3(i, c); l = Overlap3(i, f);"]


@dataclass(frozen=True)
class Then:
    a: Interval3
    b: Interval3

    def __post_init__(self):
        assert self.a.y < self.b.x


@dataclass(frozen=True)
class Tangent:
    a: Interval3
    b: Interval3

    def __post_init__(self):
        assert self.a.y == self.b.x


@dataclass(frozen=True)
class Kissing:
    a: Interval3
    b: Interval3

    def __post_init__(self):
        if isinstance(self.a.y, int):
            return

        model, left, right = self.a.y.to_left_right(self.b.x)
        model.add(left + 1 == right)
        assert model.check_satisfiability()


# @pytest.mark.skipif(not os.getenv('CI'), reason="This test takes too long, it is for CI only")
# def test_super_compound_3():
#     theories = equivalib.generate_sentences([Interval3, Then, Tangent, Kissing])
#     assert len(theories) == 54


# def test_super_compound_maxgreedy1():
#     theories = equivalib.generate_sentences([Interval3, Then])
#     strings = list(map(str, map(equivalib.arbitrary_collapse, theories)))

#     assert len(theories) == 1
#     dedup = list(set(strings))
#     assert len(dedup) == len(strings)
#     assert sorted(dedup) == sorted(strings)
#     assert strings \
#         == ["a = 1; b = 2; c = Interval3('A', a, b); d = 3; e = 4; f = Interval3('B', d, e); g = 8; h = 9; i = Interval3('C', g, h); j = Then(c, f); k = Then(c, i); l = Then(f, i);"]

# @dataclass(frozen=True)
# class IntervalMany:
#     name: Union[Literal["A"], Literal["B"], Literal["C"], Literal["D"], Literal["E"], Literal["F"], Literal["G"], Literal["H"]]
#     x: BoundedInt[Literal[1], Literal[9]] = supervalue()
#     y: BoundedInt[Literal[1], Literal[9]] = supervalue()

#     def __post_init__(self):
#         assert self.y > self.x


# @dataclass(frozen=True)
# class ThenMany:
#     a: IntervalMany
#     b: IntervalMany

#     def __post_init__(self):
#         assert self.a.y < self.b.x


# @dataclass(frozen=True)
# class TangentMany:
#     a: IntervalMany
#     b: IntervalMany

#     def __post_init__(self):
#         assert self.a.y == self.b.x


# @dataclass(frozen=True)
# class KissingMany:
#     a: IntervalMany
#     b: IntervalMany

#     def __post_init__(self):
#         if isinstance(self.a.y, int):
#             return

#         model, left, right = self.a.y.to_left_right(self.b.x)
#         model.add(left + 1 == right)
#         assert model.check_satisfiability()


# @pytest.mark.skipif(not os.getenv('CI'), reason="This test takes too long, it is for CI only")
# def test_super_compound_manygreedy_maxgreedy1():
#     theories = equivalib.generate_sentences([IntervalMany, ThenMany, TangentMany, KissingMany])
#     assert len(theories) == 1261
