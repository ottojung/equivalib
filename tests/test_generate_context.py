
from dataclasses import dataclass
from typing import Tuple, Literal, Union
import pytest
import equivalib
from equivalib import BoundedInt


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



@dataclass(frozen=True)
class Inted:
    is_yes: bool
    confidence: BoundedInt[Literal[1], Literal[20]]


def test_ints():
    ctx = equivalib.generate_context([Inted])
    assert ctx.assignments \
        == {'a': Inted(False, 1),
            'b': Inted(False, 2),
            'c': Inted(False, 3),
            'd': Inted(False, 4),
            'e': Inted(False, 5),
            'f': Inted(False, 6),
            'g': Inted(False, 7),
            'h': Inted(False, 8),
            'i': Inted(False, 9),
            'j': Inted(False, 10),
            'k': Inted(False, 11),
            'l': Inted(False, 12),
            'm': Inted(False, 13),
            'n': Inted(False, 14),
            'o': Inted(False, 15),
            'p': Inted(False, 16),
            'q': Inted(False, 17),
            'r': Inted(False, 18),
            's': Inted(False, 19),
            't': Inted(False, 20),
            'u': Inted(True, 1),
            'v': Inted(True, 2),
            'w': Inted(True, 3),
            'x': Inted(True, 4),
            'y': Inted(True, 5),
            'z': Inted(True, 6),
            'aa': Inted(True, 7),
            'ab': Inted(True, 8),
            'ac': Inted(True, 9),
            'ad': Inted(True, 10),
            'ae': Inted(True, 11),
            'af': Inted(True, 12),
            'ag': Inted(True, 13),
            'ah': Inted(True, 14),
            'ai': Inted(True, 15),
            'aj': Inted(True, 16),
            'ak': Inted(True, 17),
            'al': Inted(True, 18),
            'am': Inted(True, 19),
            'an': Inted(True, 20)}




@dataclass(frozen=True)
class Summary:
    first: Answer
    second: Answer


def test_compound():
    ctx = equivalib.generate_context([Answer, Summary])
    assert ctx.assignments \
        == {'a': Answer(False),
            'b': Answer(True),
            'c': Summary(Answer(False), Answer(False)),
            'd': Summary(Answer(False), Answer(True)),
            'e': Summary(Answer(True), Answer(False)),
            'f': Summary(Answer(True), Answer(True))}


@dataclass(frozen=True)
class Const:
    first: bool
    second: Literal[5]


def test_constant():
    ctx = equivalib.generate_context([Const])
    assert ctx.assignments \
        == {'a': Const(False, 5),
            'b': Const(True, 5)}


@dataclass(frozen=True)
class UnionAnswer:
    response: Union[Literal[True], Literal[False], Literal["Unsure"]]
    received: bool


def test_union1():
    ctx = equivalib.generate_context([UnionAnswer])
    assert ctx.assignments \
        == {'a': UnionAnswer(True, False),
            'b': UnionAnswer(True, True),
            'c': UnionAnswer(False, False),
            'd': UnionAnswer(False, True),
            'e': UnionAnswer('Unsure', False),
            'f': UnionAnswer('Unsure', True)}


@dataclass(frozen=True)
class RestrictedAnswer:
    is_yes: bool
    received: bool

    def __post_init__(self):
        assert self.is_yes is True


def test_restricted_answer():
    ctx = equivalib.generate_context([RestrictedAnswer])
    assert ctx.assignments \
        == {'a': RestrictedAnswer(True, False),
            'b': RestrictedAnswer(True, True)}
