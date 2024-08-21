## Copyright (C) 2023  Otto Jung
## This program is free software: you can redistribute it and/or modify it under the terms of the GNU General Public License as published by the Free Software Foundation; version 3 of the License. This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more details. You should have received a copy of the GNU General Public License along with this program.  If not, see <http://www.gnu.org/licenses/>.

import dataclasses
from typing import Iterable, Iterator, Union, Literal, Dict, Optional

from equivalib.typeform import TypeForm
from equivalib.orderedset import OrderedSet
from equivalib.partially_order import partially_order
from equivalib.read_type_information import read_type_information
from equivalib.split_type import split_type


class BannedType(Exception):
    pass


def get_types_hierarchy(types: Iterable[TypeForm]) -> Iterator[OrderedSet[TypeForm]]:
    before: Dict[TypeForm, OrderedSet[TypeForm]] = {}
    all_types: OrderedSet[TypeForm] = OrderedSet()

    def recurse_subtypes(parent: Optional[TypeForm], types: Iterable[TypeForm]) -> None:
        for typ in types:
            recurse_type(parent, typ)

    def recurse_type(parent: Optional[TypeForm], t: TypeForm) -> None:
        (base, args, _hints) = split_type(t)

        all_types.add(t)
        if parent:
            if parent in before:
                before[parent].add(t)
            else:
                before[parent] = OrderedSet([t])

        if dataclasses.is_dataclass(t):
            information = read_type_information(t)
            recurse_subtypes(t, information.values())

        elif base in (Union,):
            args2: Iterable[TypeForm] = args
            recurse_subtypes(t, args2)

        elif base in (tuple, set):
            args2: Iterable[TypeForm] = args  # type: ignore
            recurse_subtypes(t, args2)

        elif base in (int, bool, Literal):
            pass

        else:
            raise BannedType(f"Type not allowed: {base}")

    for t in types:
        recurse_type(None, t)

    return partially_order(all_types, before)
