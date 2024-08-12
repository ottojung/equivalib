
from dataclasses import dataclass
from typing import Literal
import pytest

from equivalib.all import BoundedInt, supervalue, read_type_information


@dataclass
class IntervalUnbounded:
    start: int
    end: int


def test_read_type_information_for_valid_dataclass():
    expected = {
        "start": (int, False),
        "end": (int, False),
    }

    result = read_type_information(IntervalUnbounded)
    assert result == expected, "Expected type information does not match actual result."


@dataclass
class Interval:
    start: BoundedInt[Literal[0], Literal[999]]
    end: BoundedInt[Literal[0], Literal[999]]


def test_read_type_information_for_valid_generic_dataclass():
    expected = {
        "start": (BoundedInt[Literal[0], Literal[999]], False),
        "end": (BoundedInt[Literal[0], Literal[999]], False),
    }

    result = read_type_information(Interval)
    assert result == expected, "Expected type information does not match actual result."


class CustomInterval:
    def __init__(self, start, end):
        self.start = start
        self.end = end

def test_read_type_information_for_invalid_class():
    with pytest.raises(TypeError):
        read_type_information(CustomInterval)


@dataclass
class EmptyMyType:
    pass


def test_read_type_information_empty():
    assert {} == read_type_information(EmptyMyType)


def superclass(x):
    return dataclass(x)


@dataclass
class SuperBools:
    start: bool
    end: bool = supervalue()


def test_read_type_information_for_valid_generic_super_dataclass():
    expected = {
        "start": (bool, False),
        "end": (bool, True),
    }

    result = read_type_information(SuperBools)
    assert result == expected, "Expected type information does not match actual result."
