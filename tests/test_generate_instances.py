
from dataclasses import dataclass
from typing import Any, List
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
    ctx = equivalib.GeneratorContext(assignments={})
    instances = list(equivalib.generate_instances(ctx, Answer))
    assert len(instances) == 3

    expected = [[Answer(False)], [Answer(True)],
                [Answer(False), Answer(True)]]
    assert list_memequal(instances, expected)


@dataclass(frozen=True)
class AnswerTuple:
    is_yes: bool
    is_sure: bool


def test_complex():
    ctx = equivalib.GeneratorContext(assignments={})
    instances = list(equivalib.generate_instances(ctx, AnswerTuple))
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
