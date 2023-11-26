## Copyright (C) 2023  Otto Jung
## This program is free software: you can redistribute it and/or modify it under the terms of the GNU General Public License as published by the Free Software Foundation; version 3 of the License. This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more details. You should have received a copy of the GNU General Public License along with this program.  If not, see <http://www.gnu.org/licenses/>.

from typing import Type, Generator, List, Tuple, Any, Optional
import itertools
import equivalib
from equivalib import GeneratorContext


def generate_field_values(ctx: GeneratorContext,
                          name: str,
                          type_signature: List[Type]) \
                          -> Generator[Tuple[Optional[str], Any], None, None]:
    t = type_signature[0]
    if t == bool:
        assert len(type_signature) == 1
        yield (None, False)
        yield (None, True)
    elif len(type_signature) == 1:
        yield from ((k, v) for (k, v) in ctx.assignments.items() if v == t)
    else:
        raise ValueError(f"Cannot generate values of type {type_signature!r}.")


def generate_instances_fields(ctx: GeneratorContext, t: Type) -> Generator[List[Tuple[Optional[str], Any]], None, None]:
    information = equivalib.read_type_information(t)
    for field, type_signature in information.items():
        yield list(generate_field_values(ctx, field, type_signature))


def generate_instances(ctx: GeneratorContext, t: Type) -> Generator[Any, None, None]:
    pointwise = generate_instances_fields(ctx, t)
    inputs = itertools.product(*pointwise)
    for named_arguments in inputs:
        arguments = [value for name, value in named_arguments]
        yield t(*arguments)
