
from dataclasses import dataclass
from typing import Tuple, Iterable
import equivalib.all as eqv


def list_memequal(a: Iterable[Iterable[object]], b: Iterable[Iterable[object]]) -> bool:
    return set(tuple(x) for x in a) == set(tuple(x) for x in b)


@dataclass(frozen=True)
class Answer:
    is_yes: bool


def test_simple():
    ctx = eqv.Sentence.empty()
    news = list(eqv.extend_sentence(ctx, Answer))
    instances = [list(x.assignments.values()) for x in news]
    assert len(instances) == 2

    expected = [[Answer(False)], [Answer(True)]]
    assert list_memequal(instances, expected)


@dataclass(frozen=True)
class AnswerTuple:
    is_yes: bool
    is_sure: bool


def test_complex():
    ctx = eqv.Sentence.empty()
    news = list(eqv.extend_sentence(ctx, AnswerTuple))
    instances = [list(x.assignments.values()) for x in news]
    assert len(instances) == 4

    expected = [[AnswerTuple(False, False)],
                [AnswerTuple(False, True)],
                [AnswerTuple(True, False)],
                [AnswerTuple(True, True)],
                ]

    assert list_memequal(instances, expected)



@dataclass(frozen=True)
class Tupclas:
    choices: Tuple[bool, bool]


def test_tup1():
    ctx = eqv.Sentence.empty()
    news = list(eqv.extend_sentence(ctx, Tupclas))
    sentences = list(map(str, news))
    expected = ['a = Tupclas((False, False));',
                'a = Tupclas((False, True));',
                'a = Tupclas((True, False));',
                'a = Tupclas((True, True));']
    assert list_memequal(sentences, expected)
