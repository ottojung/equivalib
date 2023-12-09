## Copyright (C) 2023  Otto Jung
## This program is free software: you can redistribute it and/or modify it under the terms of the GNU General Public License as published by the Free Software Foundation; version 3 of the License. This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more details. You should have received a copy of the GNU General Public License along with this program.  If not, see <http://www.gnu.org/licenses/>.

import dataclasses
import typing
from typing import Iterable, Generator, Union, Literal, Type, Dict, Optional
import equivalib
from equivalib import MyType, BoundedInt, OrderedSet


class BannedType(Exception):
    pass


def get_types_hierarchy(types: Iterable[MyType]) -> Generator[OrderedSet[MyType], None, None]:
    before: Dict[Type[object], OrderedSet[Type[object]]] = {}
    all_types: OrderedSet[MyType] = OrderedSet()

    def recurse_subtypes(parent: Optional[MyType], types: Iterable[type[object]]) -> None:
        for typ in types:
            recurse_type(parent, typ)

    def recurse_type(parent: Optional[MyType], t: MyType) -> None:
        base = typing.get_origin(t) or t

        if base not in (Union,):
            all_types.add(t)
            if parent:
                if parent in before:
                    before[parent].add(t)
                else:
                    before[parent] = OrderedSet([t])

        if dataclasses.is_dataclass(t):
            information = equivalib.read_type_information(t)
            recurse_subtypes(t, (x for x, _is_super in information.values()))

        elif base in (Union,):
            args = typing.get_args(t)
            recurse_subtypes(parent, args)

        elif base in (tuple, set):
            args = typing.get_args(t)
            recurse_subtypes(t, args)

        elif base in (int, bool, Literal, BoundedInt):
            pass

        else:
            raise BannedType(f"Type not allowed: {base}")

    for t in types:
        recurse_type(None, t)

    return equivalib.partially_order(all_types, before)
