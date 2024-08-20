
# mypy: disable-error-code="arg-type"

from dataclasses import dataclass
from typing import Set, Literal, Union, Tuple, Annotated
import pytest

from equivalib import MyType, ValueRange, generate_instances, Super


def run_example(typ: MyType) -> Set[object]:
    return set(generate_instances(typ))


def test_bools():
    instances = run_example(bool)
    assert instances == { False, True }


def test_integers():
    instances = run_example(Annotated[int, ValueRange(1, 9)])
    assert instances == { 1, 2, 3, 4, 5, 6, 7, 8, 9 }


def test_literal():
    instances = run_example(Literal[1])
    assert instances == { 1 }


def test_union():
    instances = run_example(Union[Literal[2], Literal[4]])
    assert instances == { 2, 4 }


def test_union_hetero():
    instances = run_example(Union[Literal[2], Literal[4], bool])
    assert instances == { 2, 4, False, True }


def test_union_same():
    instances = list(generate_instances(Union[bool, bool]))
    assert set(instances) == { False, True }
    assert len(instances) == 2


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


@dataclass(frozen=True)
class PersonB:
    brave: bool


@dataclass(frozen=True)
class GuestB:
    who: PersonB
    polite: bool


def test_compound():
    instances = run_example(GuestB)
    assert instances \
        == {GuestB(PersonB(False), False),
            GuestB(PersonB(False), True),
            GuestB(PersonB(True), False),
            GuestB(PersonB(True), True)}


@dataclass(frozen=True)
class Person:
    name: Union[Literal["Alice"], Literal["Bob"]]


def test_compound_union():
    instances = run_example(Person)
    assert instances \
        == {Person(name='Bob'), Person(name='Alice')}


@dataclass(frozen=True)
class PersonT:
    coordinates: Tuple[bool, bool]


def test_compound_tuple():
    instances = run_example(PersonT)
    assert instances \
        == {PersonT((False, True)), PersonT((True, True)), PersonT((False, False)), PersonT((True, False))}


@dataclass(frozen=True)
class PersonT2:
    coordinates: Union[Tuple[Literal[False], Literal[False]],
                       Tuple[Literal[False], Literal[True]],
                       Tuple[Literal[True], Literal[False]],
                       Tuple[Literal[True], Literal[True]],
                       ]


def test_compound_tuple_2():
    instances = run_example(PersonT2)
    assert instances \
        == {PersonT2((False, True)), PersonT2((True, True)), PersonT2((False, False)), PersonT2((True, False))}


@dataclass(frozen=True)
class Guest:
    who: Person
    polite: bool


def test_compound_2():
    instances = run_example(Guest)
    assert instances \
        == {Guest(Person('Alice'), False),
            Guest(Person('Alice'), True),
            Guest(Person('Bob'), False),
            Guest(Person('Bob'), True)}


@dataclass(frozen=True)
class Entangled:
    happy: bool
    complain: bool

    def __post_init__(self):
        assert self.happy != self.complain


def test_entangled():
    instances = run_example(Entangled)
    assert instances \
        == {Entangled(False, True),
            Entangled(True, False)}


@dataclass(frozen=True)
class EntangledPeople:
    a: Guest
    b: Guest

    def __post_init__(self):
        assert self.a.polite != self.b.polite


def test_mood():
    instances = run_example(EntangledPeople)
    assert instances \
        == {EntangledPeople(Guest(Person('Bob'), False), Guest(Person('Alice'), True)),
            EntangledPeople(Guest(Person('Bob'), True), Guest(Person('Alice'), False)),
            EntangledPeople(Guest(Person('Bob'), True), Guest(Person('Bob'), False)),
            EntangledPeople(Guest(Person('Alice'), True), Guest(Person('Alice'), False)),
            EntangledPeople(Guest(Person('Alice'), True), Guest(Person('Bob'), False)),
            EntangledPeople(Guest(Person('Alice'), False), Guest(Person('Bob'), True)),
            EntangledPeople(Guest(Person('Bob'), False), Guest(Person('Bob'), True)),
            EntangledPeople(Guest(Person('Alice'), False), Guest(Person('Alice'), True))}


@dataclass(frozen=True)
class People:
    instances: Tuple[Guest, Guest]
    entangles: EntangledPeople


def test_people():
    instances = run_example(People)
    assert len(instances) == 128



@dataclass(frozen=True)
class SuperMinimal:
    happy: Annotated[bool, Super]


@pytest.mark.xfail(reason="No supervalue support yet.")
def test_super_minimal():
    instances = run_example(SuperMinimal)
    assert instances \
        in [{SuperMinimal(False)}, {SuperMinimal(True)}]


@dataclass(frozen=True)
class SuperEntangled:
    happy: Annotated[bool, Super]
    complain: Annotated[bool, Super]

    def __post_init__(self):
        assert self.happy != self.complain


@pytest.mark.xfail(reason="No supervalue support yet.")
def test_super_entangled():
    instances = run_example(SuperEntangled)
    assert len(instances) == 1
    assert instances \
        in [{SuperEntangled(False, True)},
            {SuperEntangled(True, False)}]


@dataclass(frozen=True)
class SuperGuest:
    who: Person
    polite: Annotated[bool, Super]


@dataclass(frozen=True)
class SuperPeople:
    a: SuperGuest
    b: SuperGuest
    entangleda: SuperGuest
    entangledb: SuperGuest

    def __post_init__(self):
        assert self.entangleda.polite ==  self.entangledb.polite
        assert self.entangleda.who.name != self.entangledb.who.name


@pytest.mark.xfail(reason="No supervalue support yet.")
def test_superpeople():
    assert False
    instances = run_example(SuperPeople)
    assert instances \
        == {SuperPeople(SuperGuest(Person('Alice'), False), SuperGuest(Person('Alice'), False), SuperGuest(Person('Alice'), False), SuperGuest(Person('Bob'), False)),
            SuperPeople(SuperGuest(Person('Alice'), False), SuperGuest(Person('Alice'), False), SuperGuest(Person('Bob'), False), SuperGuest(Person('Alice'), False)),
            SuperPeople(SuperGuest(Person('Alice'), False), SuperGuest(Person('Bob'), False), SuperGuest(Person('Bob'), False), SuperGuest(Person('Alice'), False)),
            SuperPeople(SuperGuest(Person('Bob'), False), SuperGuest(Person('Bob'), False), SuperGuest(Person('Bob'), False), SuperGuest(Person('Alice'), False)),
            SuperPeople(SuperGuest(Person('Bob'), False), SuperGuest(Person('Alice'), False), SuperGuest(Person('Alice'), False), SuperGuest(Person('Bob'), False)),
            SuperPeople(SuperGuest(Person('Bob'), False), SuperGuest(Person('Bob'), False), SuperGuest(Person('Alice'), False), SuperGuest(Person('Bob'), False)),
            SuperPeople(SuperGuest(Person('Alice'), False), SuperGuest(Person('Bob'), False), SuperGuest(Person('Alice'), False), SuperGuest(Person('Bob'), False)),
            SuperPeople(SuperGuest(Person('Bob'), False), SuperGuest(Person('Alice'), False), SuperGuest(Person('Bob'), False), SuperGuest(Person('Alice'), False))}



@dataclass(frozen=True)
class Interval:
    name: Union[Literal["A"], Literal["B"], Literal["C"]]
    x: Annotated[int, ValueRange(1, 99), Super]
    y: Annotated[int, ValueRange(1, 99), Super]

    def __post_init__(self):
        assert self.y > self.x


@dataclass(frozen=True)
class Before:
    a: Interval
    b: Interval

    def __post_init__(self):
        assert self.a.y < self.b.x


@pytest.mark.xfail(reason="No supervalue support yet.")
def test_intervals():
    assert False
    instances = run_example(Before)
    assert instances == \
        {Before(Interval('B', 1, 2), Interval('C', 3, 4)),
         Before(Interval('C', 1, 2), Interval('B', 3, 4)),
         Before(Interval('C', 1, 2), Interval('A', 3, 4)),
         Before(Interval('B', 1, 2), Interval('A', 3, 4)),
         Before(Interval('A', 1, 2), Interval('C', 3, 4)),
         Before(Interval('A', 1, 2), Interval('B', 3, 4))}


@dataclass(frozen=True)
class Constrained:
    a: Interval
    b: Interval
    constraint: Before

    def __post_init__(self):
        assert self.a.name != self.b.name


@pytest.mark.xfail(reason="No supervalue support yet.")
def test_constrained():
    assert False
    instances = run_example(Constrained)
    assert instances \
        == {Constrained(Interval('B', 3, 4), Interval('C', 98, 99), Before(Interval('B', 3, 4), Interval('C', 98, 99))),
            Constrained(Interval('A', 1, 2), Interval('C', 98, 99), Before(Interval('A', 1, 2), Interval('C', 98, 99))),
            Constrained(Interval('B', 3, 4), Interval('C', 98, 99), Before(Interval('A', 1, 2), Interval('B', 3, 4))),
            Constrained(Interval('C', 98, 99), Interval('B', 3, 4), Before(Interval('B', 3, 4), Interval('C', 98, 99))),
            Constrained(Interval('B', 3, 4), Interval('A', 1, 2), Before(Interval('A', 1, 2), Interval('C', 98, 99))),
            Constrained(Interval('C', 98, 99), Interval('B', 3, 4), Before(Interval('A', 1, 2), Interval('B', 3, 4))),
            Constrained(Interval('C', 98, 99), Interval('A', 1, 2), Before(Interval('B', 3, 4), Interval('C', 98, 99))),
            Constrained(Interval('B', 3, 4), Interval('C', 98, 99), Before(Interval('A', 1, 2), Interval('C', 98, 99))),
            Constrained(Interval('B', 3, 4), Interval('A', 1, 2), Before(Interval('B', 3, 4), Interval('C', 98, 99))),
            Constrained(Interval('A', 1, 2), Interval('B', 3, 4), Before(Interval('B', 3, 4), Interval('C', 98, 99))),
            Constrained(Interval('C', 98, 99), Interval('A', 1, 2), Before(Interval('A', 1, 2), Interval('B', 3, 4))),
            Constrained(Interval('C', 98, 99), Interval('B', 3, 4), Before(Interval('A', 1, 2), Interval('C', 98, 99))),
            Constrained(Interval('C', 98, 99), Interval('A', 1, 2), Before(Interval('A', 1, 2), Interval('C', 98, 99))),
            Constrained(Interval('A', 1, 2), Interval('C', 98, 99), Before(Interval('B', 3, 4), Interval('C', 98, 99))),
            Constrained(Interval('A', 1, 2), Interval('C', 98, 99), Before(Interval('A', 1, 2), Interval('B', 3, 4))),
            Constrained(Interval('B', 3, 4), Interval('A', 1, 2), Before(Interval('A', 1, 2), Interval('B', 3, 4))),
            Constrained(Interval('A', 1, 2), Interval('B', 3, 4), Before(Interval('A', 1, 2), Interval('B', 3, 4))),
            Constrained(Interval('A', 1, 2), Interval('B', 3, 4), Before(Interval('A', 1, 2), Interval('C', 98, 99)))}


@dataclass(frozen=True)
class Problem:
    intervals: Set[Interval]
    constraints: Set[Before]


@pytest.mark.xfail(reason="No supervalue support yet.")
def test_interval_problem():
    assert False
    instances = list(generate_instances(Problem))
    assert len(instances) == 64
