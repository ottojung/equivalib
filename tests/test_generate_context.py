
from dataclasses import dataclass
from typing import Tuple
import pytest
import equivalib


@dataclass(frozen=True)
class Answer:
    is_yes: bool


def test_simple():
    ctx = equivalib.generate_context([Answer])
    assert ctx.assignments \
        == {'a': Answer(False),
            'b': Answer(True)}


@dataclass(frozen=True)
class AnswerTuple:
    is_yes: bool
    is_sure: bool


def test_complex():
    ctx = equivalib.generate_context([AnswerTuple])
    assert ctx.assignments \
        == {'a': AnswerTuple(False, False),
            'b': AnswerTuple(False, True),
            'c': AnswerTuple(True, False),
            'd': AnswerTuple(True, True)}


@dataclass(frozen=True)
class BadTuple:
    is_yes: bool
    is_sure: Tuple[str, str]


def test_invalid():
    with pytest.raises(ValueError):
        equivalib.generate_context([BadTuple])
