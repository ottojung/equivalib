## Copyright (C) 2023  Otto Jung
## This program is free software: you can redistribute it and/or modify it under the terms of the GNU General Public License as published by the Free Software Foundation; version 3 of the License. This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more details. You should have received a copy of the GNU General Public License along with this program.  If not, see <http://www.gnu.org/licenses/>.

import dataclasses
import typing
from dataclasses import is_dataclass
from typing import Type, List, Dict

def read_type_information(t: Type) -> Dict[str, List[Type]]:
    """
    Returns a list of fields, ziped with their type information

    Example:

    >>> @dataclass
    >>> class Interval:
    >>>     start: BoundedInt[0, 999]
    >>>     end: BoundedInt[0, 999]
    >>>
    >>> read_type_information(Interval)
    {"start": [BoundedInt, 0, 999],
     "end": [BoundedInt, 0, 999]}

    Input argument t must be a dataclass, otherwise this function raises TypeError.
    """

    if not is_dataclass(t):
        raise TypeError("read_type_information expects a dataclass type.")

    type_information = {}
    for field in dataclasses.fields(t):
        field_name = field.name

        # Retrieve the direct type annotation
        field_direct_type = field.type

        # If type is generic (e.g., BoundedInt[0, 999]), we retrieve the base type and its parameters
        field_base_type = typing.get_origin(field_direct_type)
        if field_base_type:
            field_args = typing.get_args(field_direct_type)
            type_information[field_name] = [field_base_type, *field_args]
        else:
            type_information[field_name] = [field_direct_type]

    return type_information
