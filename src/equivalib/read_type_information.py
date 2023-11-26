## Copyright (C) 2023  Otto Jung
## This program is free software: you can redistribute it and/or modify it under the terms of the GNU General Public License as published by the Free Software Foundation; version 3 of the License. This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more details. You should have received a copy of the GNU General Public License along with this program.  If not, see <http://www.gnu.org/licenses/>.

import dataclasses
from dataclasses import is_dataclass
from typing import Type, Dict

def read_type_information(t: Type) -> Dict[str, Type]:
    """
    Returns a list of fields, ziped with their type information

    Example:

    >>> @dataclass
    >>> class Interval:
    >>>     start: BoundedInt[0, 999]
    >>>     end: BoundedInt[0, 999]
    >>>
    >>> read_type_information(Interval)
    {"start": BoundedInt[0, 999],
     "end": BoundedInt[0, 999]}

    Input argument t must be a dataclass, otherwise this function raises TypeError.
    """

    if not is_dataclass(t):
        raise TypeError("read_type_information expects a dataclass type.")

    type_information = {}
    for field in dataclasses.fields(t):
        type_information[field.name] = field.type

    return type_information
