## Copyright (C) 2023  Otto Jung
## This program is free software: you can redistribute it and/or modify it under the terms of the GNU General Public License as published by the Free Software Foundation; version 3 of the License. This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more details. You should have received a copy of the GNU General Public License along with this program.  If not, see <http://www.gnu.org/licenses/>.

import dataclasses
import typing
from typing import Set, Iterable, Generator, Union, Tuple, Literal, Type, Dict
import equivalib
from equivalib import MyType, BoundedInt


class BannedType(Exception):
    pass


def get_types_hierarchy(types: Iterable[MyType]) -> Generator[Set[MyType], None, None]:
    before: Dict[Type[object], Set[Type[object]]] = {}
    all_types: Set[MyType] = set()

    def get_all_types(t: MyType) -> Generator[MyType, None, None]:
        base = typing.get_origin(t)
        args = typing.get_args(t)
        if args:
            if base:
                if base in (Union, Tuple):
                    for lsts in map(get_all_types, args):
                        yield from lsts
                elif base not in (int, bool, Literal, BoundedInt) and not dataclasses.is_dataclass(base):
                    raise BannedType(f"Type not allowed: {base}")
                else:
                    yield base
        else:
            yield t

    def recurse_type(t: MyType) -> None:
        all_types.add(t)
        if dataclasses.is_dataclass(t):
            information = equivalib.read_type_information(t)
            for value, _is_super in information.values():
                subtypes = set(get_all_types(value))
                before[t] = subtypes
                for subtype in subtypes:
                    recurse_type(subtype)

    for t in types:
        recurse_type(t)

    return equivalib.partially_order(all_types, before)
