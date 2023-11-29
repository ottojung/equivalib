## Copyright (C) 2023  Otto Jung
## This program is free software: you can redistribute it and/or modify it under the terms of the GNU General Public License as published by the Free Software Foundation; version 3 of the License. This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more details. You should have received a copy of the GNU General Public License along with this program.  If not, see <http://www.gnu.org/licenses/>.

from dataclasses import is_dataclass
import typing
from typing import Type, Generator, List, Tuple, Any, Optional, Literal, Union
import itertools
import equivalib
from equivalib import Sentence, BoundedInt, denv, Super, Constant


def generate_field_values(ctx: Sentence,
                          t: Type) \
                          -> Generator[Tuple[Optional[str], Any], None, None]:
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

    elif base_type == Super:
        assert len(args) == 1
        parameter = args[0]
        yield (None, [base_type, parameter])

    elif base_type == BoundedInt:
        assert len(args) == 2
        low, high = BoundedInt.unpack_type(base_type, args)
        for i in range(low, high + 1):
            yield (None, i)

    elif is_dataclass(base_type):
        yield from ((k, v) for (k, v) in ctx.assignments.items() if isinstance(v, t))

    else:
        raise ValueError(f"Cannot generate values of type {t!r}.")


def generate_instances_fields(ctx: Sentence, t: Type) -> Generator[List[Tuple[Optional[str], Any]], None, None]:
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


def handle_supers(ctx, name: Optional[str], value: Any) -> Tuple[Optional[str], Any]:
    if isinstance(value, list):
        parameter = value[1]
        parameter_base = typing.get_origin(parameter) or parameter
        if parameter_base in (BoundedInt, bool):
            arg = []
        else:
            arg = list(generate_field_values(ctx, parameter))

        s = Super.make(parameter, arg)
        return (s.name, s)
    else:
        return (name, value)


def add_instances(ctx: Sentence, t: Type, instances: List[Tuple[Optional[str], Any]]) -> bool:
    with denv.let(sentence = ctx):
        try:
            for named_arguments in instances:
                renamed_arguments = [handle_supers(ctx, k, v) for k, v in named_arguments]
                arguments = (value for name, value in renamed_arguments)
                instance = t(*arguments)

                name = ctx.generate_free_name()
                ctx.assignments[name] = instance
                ctx.structure[name] = (t, [name or Constant(value) for name, value in renamed_arguments])
        except AssertionError:
            return False
    return True


def extend_sentence(ctx: Sentence, t: Type) -> Generator[Sentence, None, None]:
    pointwise = generate_instances_fields(ctx, t)
    inputs = list(itertools.product(*pointwise))
    subsets = get_subsets(inputs)
    for subset in subsets:
        if subset:
            new = ctx.copy()
            if add_instances(new, t, subset):
                yield new


def extend_sentence_maxgreedily(ctx: Sentence, t: Type) -> Generator[Sentence, None, None]:
    pointwise = generate_instances_fields(ctx, t)
    inputs = list(itertools.product(*pointwise))

    for inp in inputs:
        new = ctx.copy()
        if add_instances(new, t, [inp]):
            ctx = new

    yield ctx


def extend_sentence_greedily(ctx: Sentence, t: Type) -> Generator[Sentence, None, None]:
    pointwise = generate_instances_fields(ctx, t)
    inputs = list(itertools.product(*pointwise))

    yield ctx
    for inp in inputs:
        new = ctx.copy()
        if add_instances(new, t, [inp]):
            yield new
            ctx = new
