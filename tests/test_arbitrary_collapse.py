
from dataclasses import dataclass
import equivalib
from equivalib import Super, Sentence, SentenceModel


@dataclass
class SuperEntangled2:
    a: Super[bool]
    b: Super[bool]

    def __post_init__(self):
        assert self.a != self.b


def test_super_entangled():
    theories = equivalib.generate_sentence([SuperEntangled2])

    assert len(theories) == 1

    sentence = equivalib.arbitrary_collapse(theories[0])
    assert sentence \
        in [Sentence({'a': 1, 'b': 0, 'c': SuperEntangled2(1, 0)}, SentenceModel.empty()),
            Sentence({'a': 0, 'b': 1, 'c': SuperEntangled2(0, 1)}, SentenceModel.empty())]
