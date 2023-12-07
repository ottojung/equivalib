
# pylint: disable=duplicate-code

from dataclasses import dataclass
from typing import Tuple, Literal, Union
import pytest
import equivalib
from equivalib import BoundedInt, MaxgreedyType, superfield


@dataclass(frozen=True)
class Answer:
    is_yes: bool


def test_simple():
    theories = equivalib.generate_sentences([Answer])
    expected = [{'a': Answer(False)},
                {'a': Answer(True)},
                {'a': Answer(False), 'b': Answer(True)}]
    assignments = [x.assignments for x in theories]
    assert assignments == expected


@dataclass(frozen=True)
class AnswerTuple:
    is_yes: bool
    is_sure: bool


def test_complex():
    theories = equivalib.generate_sentences([AnswerTuple])
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
        equivalib.generate_sentences([BadTuple])



@dataclass(frozen=True)
class Inted:
    is_yes: bool
    confidence: BoundedInt[Literal[1], Literal[3]]


def test_ints():
    theories = equivalib.generate_sentences([Inted])
    assert len(theories) == 63 # 2^(2*3)-1


@dataclass(frozen=True)
class Summary:
    first: Answer
    second: Answer


def test_compound():
    theories = equivalib.generate_sentences([Answer, Summary])
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
    theories = equivalib.generate_sentences([Answer, Summary2a, Summary2b])
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
    theories = equivalib.generate_sentences([Const])
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
    theories = equivalib.generate_sentences([UnionAnswer])
    assert len(theories) == 63 # 2^(3*2)-1


@dataclass(frozen=True)
class RestrictedAnswer:
    is_yes: bool
    received: bool

    def __post_init__(self):
        assert self.is_yes is True


def test_restricted_answer():
    theories = equivalib.generate_sentences([RestrictedAnswer])
    sentences = [set(x.assignments.values()) for x in theories]

    expected = [{RestrictedAnswer(True, False)},
                {RestrictedAnswer(True, True)},
                {RestrictedAnswer(True, False), RestrictedAnswer(True, True)}]

    assert sentences == expected


@dataclass(frozen=True)
class Superposed:
    value: BoundedInt[Literal[0], Literal[9]] = superfield()


def test_super_simple():
    theories = equivalib.generate_sentences([Superposed])
    sentences = [set(x.assignments.values()) for x in theories]
    assert len(sentences) == 1


@dataclass(frozen=True)
class SuperposedBounded:
    value: BoundedInt[Literal[0], Literal[9]] = superfield()

    def __post_init__(self):
        assert self.value < 5


def test_super_bounded():
    theories = equivalib.generate_sentences([SuperposedBounded])
    sentences = [set(x.assignments.values()) for x in theories]

    assert len(sentences) == 1
    assert len(sentences[0]) == 2


@dataclass(frozen=True)
class SuperEntangled:
    a: bool = superfield()
    b: bool = superfield()

    def __post_init__(self):
        assert self.a != self.b


def test_super_entangled():
    theories = equivalib.generate_sentences([SuperEntangled])
    sentences = [set(x.assignments.values()) for x in theories]

    assert len(sentences) == 1
    assert len(sentences[0]) == 3


@dataclass
class SuperEntangledBoring:
    a: bool = superfield()
    b: bool = superfield()

    def __post_init__(self):
        assert self.a == True


def test_super_entangled_boring():
    theories = equivalib.generate_sentences([SuperEntangledBoring])
    sentences = [list(x.assignments.values()) for x in theories]

    assert len(sentences) == 1
    assert len(sentences[0]) == 3


@dataclass
class Fizz:
    n: BoundedInt[Literal[1], Literal[100]]

    def __post_init__(self):
        assert self.n % 3 == 0


@dataclass
class Buzz:
    n: BoundedInt[Literal[1], Literal[100]]

    def __post_init__(self):
        assert self.n % 5 == 0


@dataclass
class FizzBuzz:
    n: BoundedInt[Literal[1], Literal[100]]

    def __post_init__(self):
        assert self.n % 5 == 0
        assert self.n % 3 == 0


def test_fizzbuzz():
    theories = equivalib.generate_sentences([MaxgreedyType(Fizz), MaxgreedyType(Buzz), MaxgreedyType(FizzBuzz)])
    sentences = [str(x) for x in theories]
    assert len(sentences) == 1
    assert len(theories[0].assignments) == 59
