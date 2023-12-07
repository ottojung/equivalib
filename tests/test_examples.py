
from dataclasses import dataclass
from typing import Set
import equivalib
from equivalib import MyType


def run_example(typ: MyType) -> Set[object]:
    return set(equivalib.generate_instances(typ))


@dataclass(frozen=True)
class Parameters:
    a: bool
    b: bool
    c: bool


def test_params():
    instances = run_example(Parameters)
    assert len(instances) == 8
    assert instances \
        == {Parameters(True, False, True),
            Parameters(False, False, False),
            Parameters(True, True, True),
            Parameters(True, False, False),
            Parameters(True, True, False),
            Parameters(False, True, True),
            Parameters(False, True, False),
            Parameters(False, False, True)}


def test_bools():
    instances = run_example(bool)
    assert instances == {False, True}


# def test_integers():
#     sentences = run_example(BoundedInt[Literal[1], Literal[9]])
#     assert sentences \
#         == {'a = 1;',
#             'a = 2;',
#             'a = 3;',
#             'a = 4;',
#             'a = 5;',
#             'a = 6;',
#             'a = 7;',
#             'a = 8;',
#             'a = 9;'}


# @dataclass
# class Person:
#     name: Union[Literal["Alice"], Literal["Bob"]]


# @dataclass
# class Answer:
#     who: Person
#     evil: bool


# def test_compound():
#     sentences = run_example(Answer)
#     assert sentences \
#         == {"a = 'Alice'; b = 'Bob'; c = False; d = True; e = Person('Alice'); f = Person('Bob'); g = Answer(e, d);",
#             "a = 'Alice'; b = 'Bob'; c = False; d = True; e = Person('Alice'); f = Person('Bob'); g = Answer(f, d);",
#             "a = 'Alice'; b = 'Bob'; c = False; d = True; e = Person('Alice'); f = Person('Bob'); g = Answer(f, c);",
#             "a = 'Alice'; b = 'Bob'; c = False; d = True; e = Person('Alice'); f = Person('Bob'); g = Answer(e, c);"}


# @dataclass
# class Entangled:
#     happy: bool
#     complain: bool

#     def __post_init__(self):
#         assert self.happy != self.complain


# def test_super_entangled():
#     sentences = run_example(Entangled)
#     assert sentences \
#         == {'a = False; b = True; c = Entangled(a, b);',
#             'a = False; b = True; c = Entangled(b, a);'}


# @dataclass(frozen=True)
# class Interval:
#     x: BoundedInt[Literal[1], Literal[3]]
#     y: BoundedInt[Literal[1], Literal[3]]

#     def __post_init__(self):
#         assert self.x < self.y


# @dataclass(frozen=True)
# class Then:
#     a: Interval
#     b: Interval

#     def __post_init__(self):
#         assert self.a.x < self.b.x


# def test_then():
#     sentences = run_example(Then)
#     assert sentences \
#         == {'a = 1; b = 2; c = 3; d = Interval(1, 2); e = Interval(1, 3); f = Interval(2, 3); g = Then(d, f);', 'a = 1; b = 2; c = 3; d = Interval(1, 2); e = Interval(1, 3); f = Interval(2, 3); g = Then(e, f);'}


# @dataclass
# class Thens:
#     thens: Set[Then]


# def test_thens():
#     sentences = run_example(Thens)
#     assert sentences \
#         == {'a = 1; b = 2; c = 3; d = Interval(1, 2); e = Interval(1, 3); f = Interval(2, 3); g = Then(d, f); h = Then(e, f); i = Thens(frozenset({Then(a=Interval(x=1, y=2), b=Interval(x=2, y=3))}));',
#             'a = 1; b = 2; c = 3; d = Interval(1, 2); e = Interval(1, 3); f = Interval(2, 3); g = Then(d, f); h = Then(e, f); i = Thens(frozenset());',
#             'a = 1; b = 2; c = 3; d = Interval(1, 2); e = Interval(1, 3); f = Interval(2, 3); g = Then(d, f); h = Then(e, f); i = Thens(frozenset({Then(a=Interval(x=1, y=3), b=Interval(x=2, y=3))}));',
#             'a = 1; b = 2; c = 3; d = Interval(1, 2); e = Interval(1, 3); f = Interval(2, 3); g = Then(d, f); h = Then(e, f); i = Thens(frozenset({Then(a=Interval(x=1, y=2), b=Interval(x=2, y=3)), Then(a=Interval(x=1, y=3), b=Interval(x=2, y=3))}));'}
