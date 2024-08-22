
# pylint: disable=duplicate-code

from dataclasses import dataclass
import random
from typing import Annotated, Iterable, Sequence
import pytest

from equivalib.all import generate_sentences, random_collapse, ValueRange, Super, Sentence, label_type_list, TypeForm


# Define the fixture to fix the random seed
@pytest.fixture(scope='function', autouse=False)
def fixed_random_seed():
    random.seed(42)
    yield
    random.seed()


def generate(types: Iterable[TypeForm]) -> Sequence[Sentence]:
    return generate_sentences(label_type_list(types))


@dataclass
class SuperEntangled:
    a: Annotated[bool, Super]
    b: Annotated[bool, Super]

    def __post_init__(self):
        assert self.a != self.b


@pytest.mark.xfail(reason="No supervalue support yet.")
def test_super_entangled():
    theories = generate([SuperEntangled])

    assert len(theories) == 1

    sentence = random_collapse(theories[0])
    assert sentence.assignments \
        in [{'a': True, 'b': False, 'c': SuperEntangled(True, False)},
            {'a': False, 'b': True, 'c': SuperEntangled(False, True)}]

    assert str(sentence) \
        in ('a = True; b = False; c = SuperEntangled(a, b);',
            'a = False; b = True; c = SuperEntangled(a, b);')




@dataclass(frozen=True)
class Interval:
    x: Annotated[int, ValueRange(1, 9), Super]
    y: Annotated[int, ValueRange(1, 9), Super]

    def __post_init__(self):
        assert self.y > self.x


@pytest.mark.xfail(reason="No supervalue support yet.")
def test_interval(fixed_random_seed): # pylint: disable=redefined-outer-name
    theories = generate([Interval])
    assert len(theories) == 1
    sentence = random_collapse(theories[0])

    assert str(sentence) \
        == 'a = 1; b = 9; c = Interval(a, b);'
