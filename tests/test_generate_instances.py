
from dataclasses import dataclass
import equivalib


@dataclass(frozen=True)
class Answer:
    is_yes: bool


def test_simple():
    ctx = equivalib.GeneratorContext(assignments={})
    instances = list(equivalib.generate_instances(ctx, Answer))
    assert len(instances) == 2
    assert set(instances) == {Answer(False), Answer(True)}


@dataclass(frozen=True)
class AnswerTuple:
    is_yes: bool
    is_sure: bool


def test_complex():
    ctx = equivalib.GeneratorContext(assignments={})
    instances = list(equivalib.generate_instances(ctx, AnswerTuple))
    assert len(instances) == 4
    assert set(instances) == {AnswerTuple(False, False),
                              AnswerTuple(False, True),
                              AnswerTuple(True, False),
                              AnswerTuple(True, True)}
