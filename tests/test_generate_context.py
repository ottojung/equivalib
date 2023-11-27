
from dataclasses import dataclass
from typing import Tuple, Literal, Union
import pytest
import equivalib
from equivalib import GeneratorContext, BoundedInt


@dataclass(frozen=True)
class Answer:
    is_yes: bool


def test_simple():
    theories = equivalib.generate_context([Answer])
    expected = [GeneratorContext({'a': Answer(False)}, None),
                GeneratorContext({'a': Answer(True)}, None),
                GeneratorContext({'a': Answer(False), 'b': Answer(True)}, None)]
    assert theories == expected


@dataclass(frozen=True)
class AnswerTuple:
    is_yes: bool
    is_sure: bool


def test_complex():
    theories = equivalib.generate_context([AnswerTuple])
    sentences = [set(x.assignments.values()) for x in theories]
    expected = [{AnswerTuple(False, False)},
                {AnswerTuple(False, True)},
                {AnswerTuple(False, True), AnswerTuple(False, False)},
                {AnswerTuple(True, False)},
                {AnswerTuple(True, False), AnswerTuple(False, False)},
                {AnswerTuple(False, True), AnswerTuple(True, False)},
                {AnswerTuple(False, True), AnswerTuple(True, False), AnswerTuple(False, False)},
                {AnswerTuple(True, True)},
                {AnswerTuple(True, True), AnswerTuple(False, False)},
                {AnswerTuple(False, True), AnswerTuple(True, True)},
                {AnswerTuple(False, True), AnswerTuple(True, True), AnswerTuple(False, False)},
                {AnswerTuple(True, False), AnswerTuple(True, True)},
                {AnswerTuple(True, False), AnswerTuple(True, True), AnswerTuple(False, False)},
                {AnswerTuple(False, True), AnswerTuple(True, False), AnswerTuple(True, True)},
                {AnswerTuple(False, True), AnswerTuple(True, False), AnswerTuple(True, True), AnswerTuple(False, False)}]

    assert sentences == expected


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
    confidence: BoundedInt[Literal[1], Literal[3]]


def test_ints():
    theories = equivalib.generate_context([Inted])
    assert len(theories) == 63 # 2^(2*3)-1


@dataclass(frozen=True)
class Summary:
    first: Answer
    second: Answer


def test_compound():
    theories = equivalib.generate_context([Answer, Summary])
    sentences = [set(x.assignments.values()) for x in theories]

    expected = [{Answer(False), Summary(Answer(False), Answer(False))},
                {Summary(Answer(True), Answer(True)), Answer(True)},
                {Answer(False), Answer(True), Summary(Answer(False), Answer(False))},
                {Answer(False), Answer(True), Summary(Answer(False), Answer(True))},
                {Answer(False), Answer(True), Summary(Answer(False), Answer(False)), Summary(Answer(False), Answer(True))},
                {Answer(False), Answer(True), Summary(Answer(True), Answer(False))},
                {Answer(False), Answer(True), Summary(Answer(False), Answer(False)), Summary(Answer(True), Answer(False))},
                {Answer(False), Answer(True), Summary(Answer(True), Answer(False)), Summary(Answer(False), Answer(True))},
                {Summary(Answer(False), Answer(True)), Summary(Answer(True), Answer(False)), Answer(True), Summary(Answer(False), Answer(False)), Answer(False)},
                {Answer(False), Answer(True), Summary(Answer(True), Answer(True))},
                {Answer(False), Answer(True), Summary(Answer(False), Answer(False)), Summary(Answer(True), Answer(True))},
                {Answer(False), Answer(True), Summary(Answer(True), Answer(True)), Summary(Answer(False), Answer(True))},
                {Summary(Answer(False), Answer(True)), Summary(Answer(True), Answer(True)), Answer(True), Summary(Answer(False), Answer(False)), Answer(False)},
                {Answer(False), Answer(True), Summary(Answer(True), Answer(True)), Summary(Answer(True), Answer(False))},
                {Summary(Answer(True), Answer(True)), Summary(Answer(True), Answer(False)), Answer(True), Summary(Answer(False), Answer(False)), Answer(False)},
                {Summary(Answer(False), Answer(True)), Summary(Answer(True), Answer(True)), Summary(Answer(True), Answer(False)), Answer(True), Answer(False)},
                {Summary(Answer(False), Answer(True)), Summary(Answer(True), Answer(True)), Summary(Answer(True), Answer(False)), Answer(True), Summary(Answer(False), Answer(False)), Answer(False)}]

    assert sentences == expected


@dataclass(frozen=True)
class Summary2a:
    elem: Answer


@dataclass(frozen=True)
class Summary2b:
    elem: Summary2a


def test_compound2():
    theories = equivalib.generate_context([Answer, Summary2a, Summary2b])
    sentences = [set(x.assignments.values()) for x in theories]
    assert len(sentences) == 7 # 2^3-1
    expected = [{Answer(False), Summary2b(Summary2a(Answer(False))), Summary2a(Answer(False))},
                {Summary2b(Summary2a(Answer(True))), Answer(True), Summary2a(Answer(True))},
                {Answer(False), Answer(True), Summary2b(Summary2a(Answer(False))), Summary2a(Answer(False))},
                {Answer(False), Answer(True), Summary2b(Summary2a(Answer(True))), Summary2a(Answer(True))},
                {Summary2a(Answer(True)), Answer(True), Summary2a(Answer(False)), Answer(False), Summary2b(Summary2a(Answer(False)))},
                {Summary2a(Answer(True)), Answer(True), Summary2b(Summary2a(Answer(True))), Summary2a(Answer(False)), Answer(False)},
                {Summary2a(Answer(True)), Answer(True), Summary2b(Summary2a(Answer(True))), Summary2a(Answer(False)), Answer(False), Summary2b(Summary2a(Answer(False)))}]
    assert sentences == expected


@dataclass(frozen=True)
class Const:
    first: bool
    second: Literal[5]


def test_constant():
    theories = equivalib.generate_context([Const])
    sentences = [set(x.assignments.values()) for x in theories]
    expected = [{Const(False, 5)},
                {Const(True, 5)},
                {Const(False, 5), Const(True, 5)}]

    assert sentences == expected


@dataclass(frozen=True)
class UnionAnswer:
    response: Union[Literal[True], Literal[False], Literal["Unsure"]]
    received: bool


def test_union1():
    theories = equivalib.generate_context([UnionAnswer])
    assert len(theories) == 63 # 2^(3*2)-1


@dataclass(frozen=True)
class RestrictedAnswer:
    is_yes: bool
    received: bool

    def __post_init__(self):
        assert self.is_yes is True


def test_restricted_answer():
    theories = equivalib.generate_context([RestrictedAnswer])
    sentences = [set(x.assignments.values()) for x in theories]

    expected = [{RestrictedAnswer(True, False)},
                {RestrictedAnswer(True, True)},
                {RestrictedAnswer(True, False), RestrictedAnswer(True, True)}]

    assert sentences == expected
