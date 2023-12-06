## Copyright (C) 2023  Otto Jung
## This program is free software: you can redistribute it and/or modify it under the terms of the GNU General Public License as published by the Free Software Foundation; version 3 of the License. This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more details. You should have received a copy of the GNU General Public License along with this program.  If not, see <http://www.gnu.org/licenses/>.

from dataclasses import is_dataclass, dataclass
import typing
from typing import Generator, List, Tuple, Optional, Literal, Union, Iterable, Sequence, Set
import itertools
import equivalib
from equivalib import Sentence, BoundedInt, denv, Super, Constant, MyType


@dataclass(frozen=True)
class Superlist:
    t: MyType


def generate_field_values(ctx: Sentence,
                          t: MyType) \
                          -> Generator[Tuple[Optional[str], Union[object, List[object]]], None, None]:
    base_type = typing.get_origin(t) or t
    args = typing.get_args(t)

    if base_type == bool:
        assert len(args) == 0
        yield (None, False)
        yield (None, True)

    elif base_type == Literal:
        assert len(args) == 1
        yield (None, args[0])

    elif base_type == Union:
        assert len(args) > 0
        for arg in args:
            yield from generate_field_values(ctx, arg)

    elif base_type in (set, Set):
        assert len(args) == 1
        subtype = args[0]
        inputs = list(generate_field_values(ctx, subtype))
        yield from map(lambda x: (None, frozenset(map(lambda y: y[1], x))), get_subsets(inputs))

    elif base_type == Super:
        assert len(args) == 1
        # parameter = args[0]
        # yield (None, [base_type, parameter])
        yield (None, Superlist(t))

    elif base_type == BoundedInt:
        assert len(args) == 2
        low, high = BoundedInt.unpack_type(base_type, args)
        for i in range(low, high + 1):
            yield (None, i)

    elif is_dataclass(base_type):
        yield from ((k, v) for (k, v) in ctx.assignments.items() if isinstance(v, t))

    else:
        raise ValueError(f"Cannot generate values of type {t!r}.")


def generate_instances_fields(ctx: Sentence, t: MyType) -> Generator[List[Tuple[Optional[str], object]], None, None]:
    information = equivalib.read_type_information(t)
    for type_signature in information.values():
        yield list(generate_field_values(ctx, type_signature))


def get_subsets(original_set):
    if len(original_set) == 0:
        return [[]]

    # Take an element of the original set
    element = original_set.pop()

    # Get all subsets without the element
    without_element = get_subsets(original_set)

    with_element = []
    for subset in without_element:
        # Add a subset with the element to a list
        new_subset = subset + [element]
        with_element.append(new_subset)

    # Combine the subsets with and without the element
    all_subsets = without_element + with_element
    return all_subsets


def handle_supers(ctx: Sentence, name: Optional[str], value: Union[object, List[object]]) -> Tuple[Optional[str], object]:
    if isinstance(value, Superlist):
        args = typing.get_args(value.t)
        parameter = args[0]
        parameter_base = typing.get_origin(parameter) or parameter
        if parameter_base in (BoundedInt, bool):
            arg = []
        else:
            arg = list(generate_field_values(ctx, parameter))

        s: Super[object] = Super.make(parameter, arg)
        return (s.name, s)
    elif isinstance(value, frozenset):
        return (name, value)
    else:
        return (name, value)


def make_instance(ctx: Sentence, t: MyType, renamed_arguments: Iterable[Tuple[Optional[str], object]]) -> None:
    struct = (t, tuple(name or Constant(value) for name, value in renamed_arguments))
    if struct in ctx.reverse:
        return

    name = ctx.generate_free_name()
    arguments = (value for name, value in renamed_arguments)
    instance = t(*arguments)
    ctx.insert_value(name, instance, struct)


def add_instances(ctx: Sentence, t: MyType, instances: Iterable[Sequence[Tuple[Optional[str], List[object]]]]) -> bool:
    with denv.let(sentence = ctx):
        try:
            for named_arguments in instances:
                renamed_arguments = [handle_supers(ctx, k, v) for k, v in named_arguments]
                make_instance(ctx, t, renamed_arguments)
        except AssertionError:
            return False
    return True


def extend_sentence(ctx: Sentence, t: MyType) -> Generator[Sentence, None, None]:
    pointwise = generate_instances_fields(ctx, t)
    inputs = list(itertools.product(*pointwise))
    subsets = get_subsets(inputs)
    for subset in subsets:
        if subset:
            new = ctx.copy()
            if add_instances(new, t, subset):
                yield new


def extend_sentence_1(ctx: Sentence, t: MyType) -> Generator[Sentence, None, None]:
    pointwise = generate_instances_fields(ctx, t)
    inputs = list(itertools.product(*pointwise))

    for inp in inputs:
        new = ctx.copy()
        if add_instances(new, t, [inp]):
            yield new


def extend_sentence_maxgreedily(ctx: Sentence, t: MyType) -> Generator[Sentence, None, None]:
    pointwise = generate_instances_fields(ctx, t)
    inputs = list(itertools.product(*pointwise))

    for inp in inputs:
        new = ctx.copy()
        if add_instances(new, t, [inp]):
            ctx = new

    yield ctx


def extend_sentence_greedily(ctx: Sentence, t: MyType) -> Generator[Sentence, None, None]:
    pointwise = generate_instances_fields(ctx, t)
    inputs = list(itertools.product(*pointwise))

    yield ctx
    for inp in inputs:
        new = ctx.copy()
        if add_instances(new, t, [inp]):
            yield new
            ctx = new
