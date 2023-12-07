
# pylint: disable=duplicate-code

from dataclasses import dataclass
from typing import Literal
import random
import pytest
import equivalib
from equivalib import BoundedInt, supervalue


# Define the fixture to fix the random seed
@pytest.fixture(scope='function', autouse=False)
def fixed_random_seed():
    random.seed(42)
    yield
    random.seed()


@dataclass
class SuperEntangled:
    a: bool = supervalue()
    b: bool = supervalue()

    def __post_init__(self):
        assert self.a != self.b


def test_super_entangled():
    theories = equivalib.generate_sentences([SuperEntangled])

    assert len(theories) == 1

    sentence = equivalib.random_collapse(theories[0])
    assert sentence.assignments \
        in [{'a': True, 'b': False, 'c': SuperEntangled(True, False)},
            {'a': False, 'b': True, 'c': SuperEntangled(False, True)}]

    assert str(sentence) \
        in ('a = True; b = False; c = SuperEntangled(a, b);',
            'a = False; b = True; c = SuperEntangled(a, b);')




@dataclass(frozen=True)
class Interval:
    x: BoundedInt[Literal[1], Literal[9]] = supervalue()
    y: BoundedInt[Literal[1], Literal[9]] = supervalue()

    def __post_init__(self):
        assert self.y > self.x


def test_interval(fixed_random_seed): # pylint: disable=redefined-outer-name
    theories = equivalib.generate_sentences([Interval])
    assert len(theories) == 1
    sentence = equivalib.random_collapse(theories[0])

    assert str(sentence) \
        == 'a = 1; b = 9; c = Interval(a, b);'
