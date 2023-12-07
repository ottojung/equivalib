
from typing import Literal, Union, Iterable
from dataclasses import dataclass
import pytest
from equivalib import get_types_hierarchy, BoundedInt, BannedType


@dataclass
class Interval:
    start: BoundedInt[Literal[0], Literal[999]]
    end: BoundedInt[Literal[0], Literal[999]]


def test_singleton():
    hierarchy = list(map(set, get_types_hierarchy([Interval])))
    assert hierarchy == [{BoundedInt[Literal[0], Literal[999]]}, {Interval}]


def test_empty():
    hierarchy = list(get_types_hierarchy([]))
    assert hierarchy == []



@dataclass
class Overlap:
    a: Interval
    b: Interval


def test_simple():
    hierarchy = list(map(set, get_types_hierarchy([Interval, Overlap])))
    assert hierarchy == [{BoundedInt[Literal[0], Literal[999]]},
                         {Interval}, {Overlap}]


def test_simple_2():
    hierarchy = list(map(set, get_types_hierarchy([Overlap])))
    assert hierarchy == [{BoundedInt[Literal[0], Literal[999]]},
                         {Interval}, {Overlap}]


@dataclass
class EmptyMyType:
    pass


@dataclass
class Overlap2:
    a: EmptyMyType
    b: EmptyMyType


def test_empty_base():
    hierarchy = list(map(set, get_types_hierarchy([EmptyMyType, Overlap2])))
    assert hierarchy == [{EmptyMyType}, {Overlap2}]


@dataclass
class UnionRec:
    a: Union[EmptyMyType, Interval]


def test_union1():
    hierarchy = list(map(set, get_types_hierarchy([EmptyMyType, Interval, UnionRec])))
    assert hierarchy == [{BoundedInt[Literal[0], Literal[999]], EmptyMyType}, {Interval}, {UnionRec}]



@dataclass
class NonUnionRec:
    a: Iterable[Interval]


def test_non_union1():
    with pytest.raises(BannedType):
        list(get_types_hierarchy([Interval, NonUnionRec]))
