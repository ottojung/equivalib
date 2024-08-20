
from dataclasses import dataclass
from typing import Annotated, Dict
import pytest

from equivalib.all import read_type_information, ValueRange, Super


@dataclass
class IntervalUnbounded:
    start: int
    end: int


def test_read_type_information_for_valid_dataclass():
    expected = {
        "start": int,
        "end": int,
    }

    result = read_type_information(IntervalUnbounded)
    assert result == expected, "Expected type information does not match actual result."


@dataclass
class Interval:
    start: Annotated[int, ValueRange(0, 999)]
    end: Annotated[int, ValueRange(0, 999)]


def test_read_type_information_for_valid_generic_dataclass():
    expected: Dict[str, object] = {
        "start": Annotated[int, ValueRange(0, 999)],
        "end": Annotated[int, ValueRange(0, 999)],
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
    end: Annotated[bool, Super]


def test_read_type_information_for_valid_generic_super_dataclass():
    expected = {
        "start": bool,
        "end": Annotated[bool, Super],
    }

    result = read_type_information(SuperBools)
    assert result == expected, "Expected type information does not match actual result."
