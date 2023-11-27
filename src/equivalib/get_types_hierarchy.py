## Copyright (C) 2023  Otto Jung
## This program is free software: you can redistribute it and/or modify it under the terms of the GNU General Public License as published by the Free Software Foundation; version 3 of the License. This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more details. You should have received a copy of the GNU General Public License along with this program.  If not, see <http://www.gnu.org/licenses/>.

import typing
from typing import Set, Type, Iterable, Generator
import equivalib

def get_types_hierarchy(types: Iterable[Type]) -> Generator[Set[Type], None, None]:
    before = {}

    def get_all_types(t: Type) -> Generator[Type, None, None]:
        base = typing.get_origin(t)
        args = typing.get_args(t)
        if args:
            if base:
                yield base
            for lsts in map(get_all_types, args):
                yield from lsts
        else:
            yield t

    for t in types:
        information = equivalib.read_type_information(t)
        all_types = [subtype for value in information.values() for subtype in get_all_types(value)]
        before[t] = set(all_types)

    return equivalib.partially_order(types, lambda t: before[t])
