
# pylint: disable=duplicate-code

from dataclasses import dataclass
from typing import Tuple, Literal, Union
import pytest
import equivalib.all as eqv
from equivalib.all import BoundedInt, supervalue


def test_primitive():
    theories = eqv.generate_sentences([bool])
    expected = [{'a': False, 'b': True}]
    assignments = [x.assignments for x in theories]
    assert assignments == expected


@dataclass(frozen=True)
class Answer:
    is_yes: bool


def test_simple():
    theories = eqv.generate_sentences([bool, Answer])
    expected = [{'a': False, 'b': True, 'c': Answer(is_yes=False), 'd': Answer(is_yes=True)}]
    assignments = [x.assignments for x in theories]
    assert assignments == expected


@dataclass(frozen=True)
class AnswerTuple:
    is_yes: bool
    is_sure: bool


def test_complex():
    theories = eqv.generate_sentences([bool, AnswerTuple])
    sentences = [set(x.assignments.values()) for x in theories]
    expected = [{False, True,
                 AnswerTuple(is_yes=False, is_sure=True),
                 AnswerTuple(is_yes=False, is_sure=False),
                 AnswerTuple(is_yes=True, is_sure=True),
                 AnswerTuple(is_yes=True, is_sure=False)}]
    assert sentences == expected


def test_complex_twice():
    theories = eqv.generate_sentences([bool, AnswerTuple])
    sentences = [set(x.assignments.values()) for x in theories]
    expected = [{False, True,
                 AnswerTuple(is_yes=False, is_sure=True),
                 AnswerTuple(is_yes=False, is_sure=False),
                 AnswerTuple(is_yes=True, is_sure=True),
                 AnswerTuple(is_yes=True, is_sure=False)}]

    assert sentences == expected


@dataclass(frozen=True)
class BadTuple:
    is_yes: bool
    is_sure: Tuple[str, str]


def test_invalid():
    with pytest.raises(ValueError):
        eqv.generate_sentences([bool, str, Tuple[str, str], BadTuple])


def test_tuple1():
    theories = eqv.generate_sentences([bool, Tuple[bool, bool]])
    sentences = set(str(x) for x in theories)
    expected = {"a = False; b = True; c = (a, a); d = (a, b); e = (b, a); f = (b, b);"}
    assert sentences == expected


@dataclass(frozen=True)
class Tuple1:
    values: Tuple[bool, bool]


def test_tuple2():
    theories = eqv.generate_sentences([bool, Tuple[bool, bool], Tuple1])
    sentences = set(str(x) for x in theories)
    expected = {"a = False; b = True; c = (a, a); d = (a, b); e = (b, a); f = (b, b); g = Tuple1(c); h = Tuple1(d); i = Tuple1(e); j = Tuple1(f);"}
    assert sentences == expected


@dataclass(frozen=True)
class Inted:
    is_yes: bool
    confidence: BoundedInt[Literal[1], Literal[3]]


def test_ints():
    theories = eqv.generate_sentences([bool, BoundedInt[Literal[1], Literal[3]], Inted])
    assert len(theories) == 1
    assert len(theories[0].assignments) == 11 == 2 + 3 + (2 * 3)


@dataclass(frozen=True)
class Summary:
    first: Answer
    second: Answer


def test_compound():
    theories = eqv.generate_sentences([bool, Answer, Summary])
    sentences = [set(x.assignments.values()) for x in theories]

    expected = \
        [{False, True,
          Answer(is_yes=True),  Answer(is_yes=False),
          Summary(first=Answer(is_yes=False), second=Answer(is_yes=True)),
          Summary(first=Answer(is_yes=True), second=Answer(is_yes=True)),
          Summary(first=Answer(is_yes=True), second=Answer(is_yes=False)),
          Summary(first=Answer(is_yes=False), second=Answer(is_yes=False))}]

    assert sentences == expected


@dataclass(frozen=True)
class Summary2a:
    elem: Answer


@dataclass(frozen=True)
class Summary2b:
    elem: Summary2a


def test_compound2():
    theories = eqv.generate_sentences([bool, Answer, Summary2a, Summary2b])
    sentences = [set(x.assignments.values()) for x in theories]
    assert len(sentences) == 1

    expected = [{False, True, Summary2a(elem=Answer(is_yes=True)), Answer(is_yes=True), Summary2b(elem=Summary2a(elem=Answer(is_yes=True))), Summary2a(elem=Answer(is_yes=False)), Answer(is_yes=False), Summary2b(elem=Summary2a(elem=Answer(is_yes=False)))}]
    assert sentences == expected


@dataclass(frozen=True)
class Const:
    first: bool
    second: Literal[5]


def test_constant():
    theories = eqv.generate_sentences([bool, Literal[5], Const])
    sentences = [set(x.assignments.values()) for x in theories]
    expected = [{False, True, 5, Const(first=True, second=5), Const(first=False, second=5)}]
    assert sentences == expected


@dataclass(frozen=True)
class UnionAnswer:
    response: Union[Literal[True], Literal[False], Literal["Unsure"]]
    received: bool


def test_union1():
    theories = eqv.generate_sentences([bool, Literal[True], Literal[False], Literal["Unsure"], UnionAnswer])
    assert len(theories) == 1
    assert len(theories[0].assignments) == 11


@dataclass(frozen=True)
class RestrictedAnswer:
    is_yes: bool
    received: bool

    def __post_init__(self):
        assert self.is_yes is True


def test_restricted_answer():
    theories = eqv.generate_sentences([bool, RestrictedAnswer])
    sentences = [set(x.assignments.values()) for x in theories]
    expected = [{False, True, RestrictedAnswer(is_yes=True, received=True), RestrictedAnswer(is_yes=True, received=False)}]

    assert sentences == expected


@dataclass(frozen=True)
class Superposed:
    value: BoundedInt[Literal[0], Literal[9]] = supervalue()


@pytest.mark.xfail(reason="No supervalue support yet.")
def test_super_simple():
    theories = eqv.generate_sentences([Superposed])
    sentences = [set(x.assignments.values()) for x in theories]
    assert len(sentences) == 1


@dataclass(frozen=True)
class SuperposedBounded:
    value: BoundedInt[Literal[0], Literal[9]] = supervalue()

    def __post_init__(self):
        assert self.value < 5


@pytest.mark.xfail(reason="No supervalue support yet.")
def test_super_bounded():
    theories = eqv.generate_sentences([SuperposedBounded])
    sentences = [set(x.assignments.values()) for x in theories]

    assert len(sentences) == 1
    assert len(sentences[0]) == 2


@dataclass(frozen=True)
class SuperEntangled:
    a: bool = supervalue()
    b: bool = supervalue()

    def __post_init__(self):
        assert self.a != self.b


@pytest.mark.xfail(reason="No supervalue support yet.")
def test_super_entangled():
    theories = eqv.generate_sentences([SuperEntangled])
    sentences = [set(x.assignments.values()) for x in theories]

    assert len(sentences) == 1
    assert len(sentences[0]) == 3


@dataclass
class SuperEntangledBoring:
    a: bool = supervalue()
    b: bool = supervalue()

    def __post_init__(self):
        assert self.a == True


@pytest.mark.xfail(reason="No supervalue support yet.")
def test_super_entangled_boring():
    theories = eqv.generate_sentences([SuperEntangledBoring])
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
    theories = eqv.generate_sentences([BoundedInt[Literal[1], Literal[100]], Fizz, Buzz, FizzBuzz])
    sentences = [str(x) for x in theories]
    assert len(sentences) == 1
    assert len(theories[0].assignments) == 159
