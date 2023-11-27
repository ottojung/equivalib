
from dataclasses import dataclass
from typing import Tuple
import pytest
import equivalib
from equivalib import GeneratorContext


@dataclass(frozen=True)
class Answer:
    is_yes: bool


def test_simple():
    theories = equivalib.generate_context([Answer])
    expected = [GeneratorContext({}),
                GeneratorContext({'a': Answer(False)}),
                GeneratorContext({'a': Answer(True)}),
                GeneratorContext({'a': Answer(False), 'b': Answer(True)})]
    assert theories == expected


# @dataclass(frozen=True)
# class AnswerTuple:
#     is_yes: bool
#     is_sure: bool


# def test_complex():
#     ctx = equivalib.generate_context([AnswerTuple])
#     assert ctx.assignments \
#         == {'a': AnswerTuple(False, False),
#             'b': AnswerTuple(False, True),
#             'c': AnswerTuple(True, False),
#             'd': AnswerTuple(True, True)}


@dataclass(frozen=True)
class BadTuple:
    is_yes: bool
    is_sure: Tuple[str, str]


def test_invalid():
    with pytest.raises(ValueError):
        equivalib.generate_context([BadTuple])



# @dataclass(frozen=True)
# class Inted:
#     is_yes: bool
#     confidence: BoundedInt[Literal[1], Literal[3]]


# def test_ints():
#     theories = equivalib.generate_context([Inted])

#     assert len(theories) == 64

#     # [[], [GeneratorContext({'a': Inted(False, 1)})], [GeneratorContext({'a': Inted(False, 2)})], [GeneratorContext({'a': Inted(False, 1)}), GeneratorContext({'a': Inted(False, 2)})], [GeneratorContext({'a': Inted(False, 3)})], [GeneratorContext({'a': Inted(False, 1)}), GeneratorContext({'a': Inted(False, 3)})], [GeneratorContext({'a': Inted(False, 2)}), GeneratorContext({'a': Inted(False, 3)})], [GeneratorContext({'a': Inted(False, 1)}), GeneratorContext({'a': Inted(False, 2)}), GeneratorContext({'a': Inted(False, 3)})], [GeneratorContext({'a': Inted(True, 1)})], [GeneratorContext({'a': Inted(False, 1)}), GeneratorContext({'a': Inted(True, 1)})], [GeneratorContext({'a': Inted(False, 2)}), GeneratorContext({'a': Inted(True, 1)})], [GeneratorContext({'a': Inted(False, 1)}), GeneratorContext({'a': Inted(False, 2)}), GeneratorContext({'a': Inted(True, 1)})], [GeneratorContext({'a': Inted(False, 3)}), GeneratorContext({'a': Inted(True, 1)})], [GeneratorContext({'a': Inted(False, 1)}), GeneratorContext({'a': Inted(False, 3)}), GeneratorContext({'a': Inted(True, 1)})], [GeneratorContext({'a': Inted(False, 2)}), GeneratorContext({'a': Inted(False, 3)}), GeneratorContext({'a': Inted(True, 1)})], [GeneratorContext({'a': Inted(False, 1)}), GeneratorContext({'a': Inted(False, 2)}), GeneratorContext({'a': Inted(False, 3)}), GeneratorContext({'a': Inted(True, 1)})], [GeneratorContext({'a': Inted(True, 2)})], [GeneratorContext({'a': Inted(False, 1)}), GeneratorContext({'a': Inted(True, 2)})], [GeneratorContext({'a': Inted(False, 2)}), GeneratorContext({'a': Inted(True, 2)})], [GeneratorContext({'a': Inted(False, 1)}), GeneratorContext({'a': Inted(False, 2)}), GeneratorContext({'a': Inted(True, 2)})], [GeneratorContext({'a': Inted(False, 3)}), GeneratorContext({'a': Inted(True, 2)})], [GeneratorContext({'a': Inted(False, 1)}), GeneratorContext({'a': Inted(False, 3)}), GeneratorContext({'a': Inted(True, 2)})], [GeneratorContext({'a': Inted(False, 2)}), GeneratorContext({'a': Inted(False, 3)}), GeneratorContext({'a': Inted(True, 2)})], [GeneratorContext({'a': Inted(False, 1)}), GeneratorContext({'a': Inted(False, 2)}), GeneratorContext({'a': Inted(False, 3)}), GeneratorContext({'a': Inted(True, 2)})], [GeneratorContext({'a': Inted(True, 1)}), GeneratorContext({'a': Inted(True, 2)})], [GeneratorContext({'a': Inted(False, 1)}), GeneratorContext({'a': Inted(True, 1)}), GeneratorContext({'a': Inted(True, 2)})], [GeneratorContext({'a': Inted(False, 2)}), GeneratorContext({'a': Inted(True, 1)}), GeneratorContext({'a': Inted(True, 2)})], [GeneratorContext({'a': Inted(False, 1)}), GeneratorContext({'a': Inted(False, 2)}), GeneratorContext({'a': Inted(True, 1)}), GeneratorContext({'a': Inted(True, 2)})], [GeneratorContext({'a': Inted(False, 3)}), GeneratorContext({'a': Inted(True, 1)}), GeneratorContext({'a': Inted(True, 2)})], [GeneratorContext({'a': Inted(False, 1)}), GeneratorContext({'a': Inted(False, 3)}), GeneratorContext({'a': Inted(True, 1)}), GeneratorContext({'a': Inted(True, 2)})], [GeneratorContext({'a': Inted(False, 2)}), GeneratorContext({'a': Inted(False, 3)}), GeneratorContext({'a': Inted(True, 1)}), GeneratorContext({'a': Inted(True, 2)})], [GeneratorContext({'a': Inted(False, 1)}), GeneratorContext({'a': Inted(False, 2)}), GeneratorContext({'a': Inted(False, 3)}), GeneratorContext({'a': Inted(True, 1)}), GeneratorContext({'a': Inted(True, 2)})], [GeneratorContext({'a': Inted(True, 3)})], [GeneratorContext({'a': Inted(False, 1)}), GeneratorContext({'a': Inted(True, 3)})], [GeneratorContext({'a': Inted(False, 2)}), GeneratorContext({'a': Inted(True, 3)})], [GeneratorContext({'a': Inted(False, 1)}), GeneratorContext({'a': Inted(False, 2)}), GeneratorContext({'a': Inted(True, 3)})], [GeneratorContext({'a': Inted(False, 3)}), GeneratorContext({'a': Inted(True, 3)})], [GeneratorContext({'a': Inted(False, 1)}), GeneratorContext({'a': Inted(False, 3)}), GeneratorContext({'a': Inted(True, 3)})], [GeneratorContext({'a': Inted(False, 2)}), GeneratorContext({'a': Inted(False, 3)}), GeneratorContext({'a': Inted(True, 3)})], [GeneratorContext({'a': Inted(False, 1)}), GeneratorContext({'a': Inted(False, 2)}), GeneratorContext({'a': Inted(False, 3)}), GeneratorContext({'a': Inted(True, 3)})], [GeneratorContext({'a': Inted(True, 1)}), GeneratorContext({'a': Inted(True, 3)})], [GeneratorContext({'a': Inted(False, 1)}), GeneratorContext({'a': Inted(True, 1)}), GeneratorContext({'a': Inted(True, 3)})], [GeneratorContext({'a': Inted(False, 2)}), GeneratorContext({'a': Inted(True, 1)}), GeneratorContext({'a': Inted(True, 3)})], [GeneratorContext({'a': Inted(False, 1)}), GeneratorContext({'a': Inted(False, 2)}), GeneratorContext({'a': Inted(True, 1)}), GeneratorContext({'a': Inted(True, 3)})], [GeneratorContext({'a': Inted(False, 3)}), GeneratorContext({'a': Inted(True, 1)}), GeneratorContext({'a': Inted(True, 3)})], [GeneratorContext({'a': Inted(False, 1)}), GeneratorContext({'a': Inted(False, 3)}), GeneratorContext({'a': Inted(True, 1)}), GeneratorContext({'a': Inted(True, 3)})], [GeneratorContext({'a': Inted(False, 2)}), GeneratorContext({'a': Inted(False, 3)}), GeneratorContext({'a': Inted(True, 1)}), GeneratorContext({'a': Inted(True, 3)})], [GeneratorContext({'a': Inted(False, 1)}), GeneratorContext({'a': Inted(False, 2)}), GeneratorContext({'a': Inted(False, 3)}), GeneratorContext({'a': Inted(True, 1)}), GeneratorContext({'a': Inted(True, 3)})], [GeneratorContext({'a': Inted(True, 2)}), GeneratorContext({'a': Inted(True, 3)})], [GeneratorContext({'a': Inted(False, 1)}), GeneratorContext({'a': Inted(True, 2)}), GeneratorContext({'a': Inted(True, 3)})], [GeneratorContext({'a': Inted(False, 2)}), GeneratorContext({'a': Inted(True, 2)}), GeneratorContext({'a': Inted(True, 3)})], [GeneratorContext({'a': Inted(False, 1)}), GeneratorContext({'a': Inted(False, 2)}), GeneratorContext({'a': Inted(True, 2)}), GeneratorContext({'a': Inted(True, 3)})], [GeneratorContext({'a': Inted(False, 3)}), GeneratorContext({'a': Inted(True, 2)}), GeneratorContext({'a': Inted(True, 3)})], [GeneratorContext({'a': Inted(False, 1)}), GeneratorContext({'a': Inted(False, 3)}), GeneratorContext({'a': Inted(True, 2)}), GeneratorContext({'a': Inted(True, 3)})], [GeneratorContext({'a': Inted(False, 2)}), GeneratorContext({'a': Inted(False, 3)}), GeneratorContext({'a': Inted(True, 2)}), GeneratorContext({'a': Inted(True, 3)})], [GeneratorContext({'a': Inted(False, 1)}), GeneratorContext({'a': Inted(False, 2)}), GeneratorContext({'a': Inted(False, 3)}), GeneratorContext({'a': Inted(True, 2)}), GeneratorContext({'a': Inted(True, 3)})], [GeneratorContext({'a': Inted(True, 1)}), GeneratorContext({'a': Inted(True, 2)}), GeneratorContext({'a': Inted(True, 3)})], [GeneratorContext({'a': Inted(False, 1)}), GeneratorContext({'a': Inted(True, 1)}), GeneratorContext({'a': Inted(True, 2)}), GeneratorContext({'a': Inted(True, 3)})], [GeneratorContext({'a': Inted(False, 2)}), GeneratorContext({'a': Inted(True, 1)}), GeneratorContext({'a': Inted(True, 2)}), GeneratorContext({'a': Inted(True, 3)})], [GeneratorContext({'a': Inted(False, 1)}), GeneratorContext({'a': Inted(False, 2)}), GeneratorContext({'a': Inted(True, 1)}), GeneratorContext({'a': Inted(True, 2)}), GeneratorContext({'a': Inted(True, 3)})], [GeneratorContext({'a': Inted(False, 3)}), GeneratorContext({'a': Inted(True, 1)}), GeneratorContext({'a': Inted(True, 2)}), GeneratorContext({'a': Inted(True, 3)})], [GeneratorContext({'a': Inted(False, 1)}), GeneratorContext({'a': Inted(False, 3)}), GeneratorContext({'a': Inted(True, 1)}), GeneratorContext({'a': Inted(True, 2)}), GeneratorContext({'a': Inted(True, 3)})], [GeneratorContext({'a': Inted(False, 2)}), GeneratorContext({'a': Inted(False, 3)}), GeneratorContext({'a': Inted(True, 1)}), GeneratorContext({'a': Inted(True, 2)}), GeneratorContext({'a': Inted(True, 3)})], [GeneratorContext({'a': Inted(False, 1)}), GeneratorContext({'a': Inted(False, 2)}), GeneratorContext({'a': Inted(False, 3)}), GeneratorContext({'a': Inted(True, 1)}), GeneratorContext({'a': Inted(True, 2)}), GeneratorContext({'a': Inted(True, 3)})]]
#     # print("")
#     # print("")
#     # print(f"theories: {theories}")
#     # print("")
#     # print("")


# # @dataclass(frozen=True)
# # class Summary:
# #     first: Answer
# #     second: Answer


# # def test_compound():
# #     ctx = equivalib.generate_context([Answer, Summary])
# #     assert ctx.assignments \
# #         == {'a': Answer(False),
# #             'b': Answer(True),
# #             'c': Summary(Answer(False), Answer(False)),
# #             'd': Summary(Answer(False), Answer(True)),
# #             'e': Summary(Answer(True), Answer(False)),
# #             'f': Summary(Answer(True), Answer(True))}


# # @dataclass(frozen=True)
# # class Const:
# #     first: bool
# #     second: Literal[5]


# # def test_constant():
# #     ctx = equivalib.generate_context([Const])
# #     assert ctx.assignments \
# #         == {'a': Const(False, 5),
# #             'b': Const(True, 5)}


# # @dataclass(frozen=True)
# # class UnionAnswer:
# #     response: Union[Literal[True], Literal[False], Literal["Unsure"]]
# #     received: bool


# # def test_union1():
# #     ctx = equivalib.generate_context([UnionAnswer])
# #     assert ctx.assignments \
# #         == {'a': UnionAnswer(True, False),
# #             'b': UnionAnswer(True, True),
# #             'c': UnionAnswer(False, False),
# #             'd': UnionAnswer(False, True),
# #             'e': UnionAnswer('Unsure', False),
# #             'f': UnionAnswer('Unsure', True)}


# # @dataclass(frozen=True)
# # class RestrictedAnswer:
# #     is_yes: bool
# #     received: bool

# #     def __post_init__(self):
# #         assert self.is_yes is True


# # def test_restricted_answer():
# #     ctx = equivalib.generate_context([RestrictedAnswer])
# #     assert ctx.assignments \
# #         == {'a': RestrictedAnswer(True, False),
# #             'b': RestrictedAnswer(True, True)}
