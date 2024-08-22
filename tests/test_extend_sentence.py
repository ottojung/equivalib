
from dataclasses import dataclass
from typing import Tuple, Iterable, Iterator
import equivalib.all as eqv


def list_memequal(a: Iterable[Iterable[object]], b: Iterable[Iterable[object]]) -> bool:
    return set(tuple(x) for x in a) == set(tuple(x) for x in b)


def extend(ctx: eqv.Sentence, t: eqv.TypeForm) -> Iterator[eqv.Sentence]:
    lt = eqv.label_type(t)
    return eqv.extend_sentence(ctx, lt)


@dataclass(frozen=True)
class Answer:
    is_yes: bool


def test_simple():
    ctx = eqv.Sentence.empty()
    list(extend(ctx, bool))
    news = list(extend(ctx, Answer))
    instances = [list(x.assignments.values()) for x in news]
    assert len(instances) == 1
    expected = [[False, True, Answer(is_yes=False), Answer(is_yes=True)]]
    assert list_memequal(instances, expected)


@dataclass(frozen=True)
class AnswerTuple:
    is_yes: bool
    is_sure: bool


def test_complex():
    ctx = eqv.Sentence.empty()
    list(extend(ctx, bool))
    news = list(extend(ctx, AnswerTuple))
    instances = [list(x.assignments.values()) for x in news]
    assert len(instances) == 1

    expected = [[False, True,
                 AnswerTuple(False, False),
                 AnswerTuple(False, True),
                 AnswerTuple(True, False),
                 AnswerTuple(True, True),
                 ]]

    assert list_memequal(instances, expected)


def test_complex_twice():
    ctx = eqv.Sentence.empty()

    news_1 = list(extend(ctx, bool))
    assert len(news_1) == 1

    instances_1 = [list(x.assignments.values()) for x in news_1]
    expected_1 = [[False, True]]

    assert list_memequal(instances_1, expected_1)

    first = news_1[0]
    news_2 = list(extend(first, AnswerTuple))

    instances_2 = [list(x.assignments.values()) for x in news_2]
    expected_2 = [[False, True,
                   AnswerTuple(False, False),
                   AnswerTuple(False, True),
                   AnswerTuple(True, False),
                   AnswerTuple(True, True),
                   ]]

    assert list_memequal(instances_2, expected_2)


@dataclass(frozen=True)
class Tupclas:
    choices: Tuple[bool, bool]


def test_tup1():
    ctx = eqv.Sentence.empty()
    list(extend(ctx, bool))
    list(extend(ctx, Tuple[bool, bool]))
    news = list(extend(ctx, Tupclas))
    sentences = list(map(str, news))
    expected = ["a = False; b = True; c = (a, a); d = (a, b); e = (b, a); f = (b, b); g = Tupclas(c); h = Tupclas(d); i = Tupclas(e); j = Tupclas(f);"]
    assert list_memequal(sentences, expected)
