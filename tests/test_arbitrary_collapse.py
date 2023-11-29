
from dataclasses import dataclass
import equivalib
from equivalib import Super


@dataclass
class SuperEntangled2:
    a: Super[bool]
    b: Super[bool]

    def __post_init__(self):
        assert self.a != self.b


def test_super_entangled():
    theories = equivalib.generate_sentences([SuperEntangled2])

    assert len(theories) == 1

    sentence = equivalib.arbitrary_collapse(theories[0])
    assert sentence.assignments \
        in [{'a': 1, 'b': 0, 'c': SuperEntangled2(1, 0)},
            {'a': 0, 'b': 1, 'c': SuperEntangled2(0, 1)}]
