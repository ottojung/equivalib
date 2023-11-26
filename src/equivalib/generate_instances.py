## Copyright (C) 2023  Otto Jung
## This program is free software: you can redistribute it and/or modify it under the terms of the GNU General Public License as published by the Free Software Foundation; version 3 of the License. This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more details. You should have received a copy of the GNU General Public License along with this program.  If not, see <http://www.gnu.org/licenses/>.

import typing
from typing import Type, Generator, List, Tuple, Any, Optional, Literal, Union
import itertools
import equivalib
from equivalib import GeneratorContext, BoundedInt


def generate_field_values(ctx: GeneratorContext,
                          name: str,
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
            yield from generate_field_values(ctx, name, arg)
    elif base_type == BoundedInt:
        assert len(args) == 2
        low_l, high_l = args
        low, high = (typing.get_args(low_l)[0], typing.get_args(high_l)[0])
        assert isinstance(low, int)
        assert isinstance(high, int)
        for i in range(low, high + 1):
            yield (None, i)
    elif len(args) == 0:
        yield from ((k, v) for (k, v) in ctx.assignments.items() if isinstance(v, t))
    else:
        raise ValueError(f"Cannot generate values of type {t!r}.")


def generate_instances_fields(ctx: GeneratorContext, t: Type) -> Generator[List[Tuple[Optional[str], Any]], None, None]:
    information = equivalib.read_type_information(t)
    for field, type_signature in information.items():
        yield list(generate_field_values(ctx, field, type_signature))


def generate_instances(ctx: GeneratorContext, t: Type) -> Generator[Any, None, None]:
    pointwise = generate_instances_fields(ctx, t)
    inputs = itertools.product(*pointwise)
    for named_arguments in inputs:
        arguments = [value for name, value in named_arguments]
        try:
            ret = t(*arguments)
            yield ret
        except AssertionError:
            pass
