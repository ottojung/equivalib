
from typing import Union, Iterable, Tuple, Annotated
from dataclasses import dataclass
import pytest
from equivalib.all import get_types_hierarchy, BannedType, ValueRange


@dataclass
class Interval:
    start: Annotated[int, ValueRange(0, 999)]
    end: Annotated[int, ValueRange(0, 999)]


def test_singleton():
    hierarchy = list(map(set, get_types_hierarchy([Interval])))
    assert hierarchy == [{Annotated[int, ValueRange(0, 999)]}, {Interval}]


def test_empty():
    hierarchy = list(get_types_hierarchy([]))
    assert hierarchy == []



@dataclass
class Overlap:
    a: Interval
    b: Interval


def test_simple():
    hierarchy = list(map(set, get_types_hierarchy([Interval, Overlap])))
    assert hierarchy == [{Annotated[int, ValueRange(0, 999)]},
                         {Interval}, {Overlap}]


def test_simple_2():
    hierarchy = list(map(set, get_types_hierarchy([Overlap])))
    assert hierarchy == [{Annotated[int, ValueRange(0, 999)]},
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
class TupleRec:
    a: Tuple[EmptyMyType, Interval]


def test_tuple1():
    hierarchy = list(map(set, get_types_hierarchy([EmptyMyType, Interval, TupleRec])))
    assert hierarchy == [{Annotated[int, ValueRange(0, 999)], EmptyMyType}, {Interval}, {Tuple[EmptyMyType, Interval]}, {TupleRec}]


@dataclass
class UnionRec:
    a: Union[EmptyMyType, Interval]


def test_union1():
    hierarchy = list(map(set, get_types_hierarchy([EmptyMyType, Interval, UnionRec])))
    assert hierarchy == [{Annotated[int, ValueRange(0, 999)], EmptyMyType}, {Interval}, {Union[EmptyMyType, Interval]}, {UnionRec}]


@dataclass
class NonUnionRec:
    a: Iterable[Interval]


def test_non_union1():
    with pytest.raises(BannedType):
        list(get_types_hierarchy([Interval, NonUnionRec]))
