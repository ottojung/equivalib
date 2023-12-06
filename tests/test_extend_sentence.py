
from dataclasses import dataclass
from typing import Any, List, Set
import equivalib


def list_memequal(a: List[Any], b: List[Any]) -> bool:
    if len(a) != len(b):
        return False

    for x in a:
        if x not in b:
            return False

    return True


@dataclass(frozen=True)
class Answer:
    is_yes: bool


def test_simple():
    ctx = equivalib.Sentence.empty()
    news = list(equivalib.extend_sentence(ctx, Answer))
    instances = [list(x.assignments.values()) for x in news]
    assert len(instances) == 3

    expected = [[Answer(False)], [Answer(True)],
                [Answer(False), Answer(True)]]
    assert list_memequal(instances, expected)


@dataclass(frozen=True)
class AnswerTuple:
    is_yes: bool
    is_sure: bool


def test_complex():
    ctx = equivalib.Sentence.empty()
    news = list(equivalib.extend_sentence(ctx, AnswerTuple))
    instances = [list(x.assignments.values()) for x in news]
    assert len(instances) == 15

    expected = [[AnswerTuple(False, False)],
                [AnswerTuple(False, True)],
                [AnswerTuple(False, False), AnswerTuple(False, True)],
                [AnswerTuple(True, False)],
                [AnswerTuple(False, False), AnswerTuple(True, False)],
                [AnswerTuple(False, True), AnswerTuple(True, False)],
                [AnswerTuple(False, False), AnswerTuple(False, True), AnswerTuple(True, False)],
                [AnswerTuple(True, True)],
                [AnswerTuple(False, False), AnswerTuple(True, True)],
                [AnswerTuple(False, True), AnswerTuple(True, True)],
                [AnswerTuple(False, False), AnswerTuple(False, True), AnswerTuple(True, True)],
                [AnswerTuple(True, False), AnswerTuple(True, True)],
                [AnswerTuple(False, False), AnswerTuple(True, False), AnswerTuple(True, True)],
                [AnswerTuple(False, True), AnswerTuple(True, False), AnswerTuple(True, True)],
                [AnswerTuple(False, False), AnswerTuple(False, True), AnswerTuple(True, False), AnswerTuple(True, True)]]

    assert list_memequal(instances, expected)



@dataclass(frozen=True)
class Setclass:
    choices: Set[bool]


def test_set1():
    ctx = equivalib.Sentence.empty()
    news = list(equivalib.extend_sentence_1(ctx, Setclass))
    sentences = list(map(str, news))

    expected = ['a = Setclass(frozenset());',
                'a = Setclass(frozenset({False}));',
                'a = Setclass(frozenset({True}));',
                'a = Setclass(frozenset({False, True}));']
    assert list_memequal(sentences, expected)


@dataclass(frozen=True)
class Setclass2:
    choice: bool
    choices: Set[bool]


def test_set2():
    ctx = equivalib.Sentence.empty()
    news = list(equivalib.extend_sentence_1(ctx, Setclass2))
    sentences = list(map(str, news))

    expected = ['a = Setclass2(False, frozenset());',
                'a = Setclass2(False, frozenset({False}));',
                'a = Setclass2(False, frozenset({True}));',
                'a = Setclass2(False, frozenset({False, True}));',
                'a = Setclass2(True, frozenset());',
                'a = Setclass2(True, frozenset({False}));',
                'a = Setclass2(True, frozenset({True}));',
                'a = Setclass2(True, frozenset({False, True}));']
    assert list_memequal(sentences, expected)
