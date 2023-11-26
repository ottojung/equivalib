
from dataclasses import dataclass
from typing import Literal
import pytest
from equivalib.bounded_int import BoundedInt
import equivalib


@dataclass
class IntervalUnbounded:
    start: int
    end: int


def test_read_type_information_for_valid_dataclass():
    expected = {
        "start": int,
        "end": int,
    }

    result = equivalib.read_type_information(IntervalUnbounded)
    assert result == expected, "Expected type information does not match actual result."


@dataclass
class Interval:
    start: BoundedInt[Literal[0], Literal[999]]
    end: BoundedInt[Literal[0], Literal[999]]


def test_read_type_information_for_valid_generic_dataclass():
    expected = {
        "start": BoundedInt[Literal[0], Literal[999]],
        "end": BoundedInt[Literal[0], Literal[999]],
    }

    result = equivalib.read_type_information(Interval)
    assert result == expected, "Expected type information does not match actual result."


class CustomInterval:
    def __init__(self, start, end):
        self.start = start
        self.end = end

def test_read_type_information_for_invalid_class():
    with pytest.raises(TypeError):
        equivalib.read_type_information(CustomInterval)


@dataclass
class EmptyType:
    pass


def test_read_type_information_empty():
    assert {} == equivalib.read_type_information(EmptyType)
