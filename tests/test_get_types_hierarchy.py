
from typing import Literal
from dataclasses import dataclass
import pytest
from equivalib import get_types_hierarchy
from equivalib.bounded_int import BoundedInt


@dataclass
class Interval:
    start: BoundedInt[Literal[0], Literal[999]]
    end: BoundedInt[Literal[0], Literal[999]]


def test_singleton():
    hierarchy = list(get_types_hierarchy([Interval]))
    assert hierarchy == [{Interval}]


def test_empty():
    hierarchy = list(get_types_hierarchy([]))
    assert hierarchy == []



@dataclass
class Overlap:
    a: Interval
    b: Interval


def test_simple():
    hierarchy = list(get_types_hierarchy([Interval, Overlap]))
    assert hierarchy == [{Interval}, {Overlap}]


@dataclass
class EmptyType:
    pass


@dataclass
class Overlap2:
    a: EmptyType
    b: EmptyType


def test_empty_base():
    hierarchy = list(get_types_hierarchy([EmptyType, Overlap2]))
    assert hierarchy == [{EmptyType}, {Overlap2}]


def test_discard_some():
    hierarchy = list(get_types_hierarchy([Overlap2]))
    assert hierarchy == [{Overlap2}]


def test_get_ground_types():
    with pytest.raises(TypeError):
        get_types_hierarchy([BoundedInt, Interval])