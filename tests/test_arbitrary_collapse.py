
from dataclasses import dataclass
from typing import Literal, Union
import equivalib
from equivalib import Super, BoundedInt


# pylint: disable=duplicate-code
@dataclass
class SuperEntangled:
    a: Super[bool]
    b: Super[bool]

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
    x: Super[BoundedInt[Literal[1], Literal[9]]]
    y: Super[BoundedInt[Literal[1], Literal[9]]]

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
    x: Super[BoundedInt[Literal[1], Literal[9]]]
    y: Super[BoundedInt[Literal[1], Literal[9]]]

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
    assert len(theories) == 17
    strings = list(map(str, map(equivalib.arbitrary_collapse, theories)))
    assert strings \
        == ['a = 1; b = 9; c = Interval2(A, a, b); d = Overlap2(c, c);',
            'a = 1; b = 9; c = Interval2(B, a, b); d = Overlap2(c, c);',
            'a = 1; b = 9; c = Interval2(A, a, b); d = 1; e = 2; f = Interval2(B, d, e); g = Overlap2(c, c);',
            'a = 1; b = 2; c = Interval2(A, a, b); d = 1; e = 9; f = Interval2(B, d, e); g = Overlap2(c, f);',
            'a = 1; b = 2; c = Interval2(A, a, b); d = 1; e = 9; f = Interval2(B, d, e); g = Overlap2(c, c); h = Overlap2(c, f);',
            'a = 1; b = 9; c = Interval2(A, a, b); d = 1; e = 2; f = Interval2(B, d, e); g = Overlap2(f, c);',
            'a = 1; b = 9; c = Interval2(A, a, b); d = 1; e = 2; f = Interval2(B, d, e); g = Overlap2(c, c); h = Overlap2(f, c);',
            'a = 1; b = 2; c = Interval2(A, a, b); d = 1; e = 2; f = Interval2(B, d, e); g = Overlap2(c, f); h = Overlap2(f, c);',
            'a = 1; b = 2; c = Interval2(A, a, b); d = 1; e = 2; f = Interval2(B, d, e); g = Overlap2(c, c); h = Overlap2(c, f); i = Overlap2(f, c);',
            'a = 1; b = 2; c = Interval2(A, a, b); d = 1; e = 9; f = Interval2(B, d, e); g = Overlap2(f, f);',
            'a = 1; b = 9; c = Interval2(A, a, b); d = 1; e = 9; f = Interval2(B, d, e); g = Overlap2(c, c); h = Overlap2(f, f);',
            'a = 1; b = 2; c = Interval2(A, a, b); d = 1; e = 9; f = Interval2(B, d, e); g = Overlap2(c, f); h = Overlap2(f, f);',
            'a = 1; b = 2; c = Interval2(A, a, b); d = 1; e = 9; f = Interval2(B, d, e); g = Overlap2(c, c); h = Overlap2(c, f); i = Overlap2(f, f);',
            'a = 1; b = 9; c = Interval2(A, a, b); d = 1; e = 2; f = Interval2(B, d, e); g = Overlap2(f, c); h = Overlap2(f, f);',
            'a = 1; b = 9; c = Interval2(A, a, b); d = 1; e = 2; f = Interval2(B, d, e); g = Overlap2(c, c); h = Overlap2(f, c); i = Overlap2(f, f);',
            'a = 1; b = 2; c = Interval2(A, a, b); d = 1; e = 2; f = Interval2(B, d, e); g = Overlap2(c, f); h = Overlap2(f, c); i = Overlap2(f, f);',
            'a = 1; b = 2; c = Interval2(A, a, b); d = 1; e = 2; f = Interval2(B, d, e); g = Overlap2(c, c); h = Overlap2(c, f); i = Overlap2(f, c); j = Overlap2(f, f);']
