
# mypy: disable-error-code="arg-type"

from dataclasses import dataclass
from typing import Set, Literal, Union, Tuple
import equivalib
from equivalib import MyType, BoundedInt, supervalue


def run_example(typ: MyType) -> Set[object]:
    return set(equivalib.generate_instances(typ))


def test_bools():
    instances = run_example(bool)
    assert instances == {False, True}


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


def test_integers():
    instances = run_example(BoundedInt[Literal[1], Literal[9]])
    assert instances == { 1, 2, 3, 4, 5, 6, 7, 8, 9 }


@dataclass(frozen=True)
class Person:
    name: Union[Literal["Alice"], Literal["Bob"]]


@dataclass(frozen=True)
class Guest:
    who: Person
    polite: bool


def test_compound():
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
class SuperEntangled:
    happy: bool = supervalue()
    complain: bool = supervalue()

    def __post_init__(self):
        assert self.happy != self.complain


def test_super_entangled():
    instances = run_example(SuperEntangled)
    assert len(instances) == 1
    assert instances \
        in [{SuperEntangled(False, True)},
            {SuperEntangled(True, False)}]


@dataclass(frozen=True)
class SuperGuest:
    who: Person
    polite: bool = supervalue()


@dataclass(frozen=True)
class SuperPeople:
    a: SuperGuest
    b: SuperGuest
    entangleda: SuperGuest
    entangledb: SuperGuest

    def __post_init__(self):
        assert self.entangleda.polite ==  self.entangledb.polite
        assert self.entangleda.who.name != self.entangledb.who.name


def test_superpeople():
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
    x: BoundedInt[Literal[1], Literal[99]] = supervalue()
    y: BoundedInt[Literal[1], Literal[99]] = supervalue()

    def __post_init__(self):
        assert self.y > self.x


@dataclass(frozen=True)
class Before:
    a: Interval
    b: Interval

    def __post_init__(self):
        assert self.a.y < self.b.x


def test_intervals():
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


def test_constrained():
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


def test_interval_problem():
    instances = list(equivalib.generate_instances(Problem))
    assert len(instances) == 64
