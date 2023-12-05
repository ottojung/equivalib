## Copyright (C) 2023  Otto Jung
## This program is free software: you can redistribute it and/or modify it under the terms of the GNU General Public License as published by the Free Software Foundation; version 3 of the License. This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more details. You should have received a copy of the GNU General Public License along with this program.  If not, see <http://www.gnu.org/licenses/>.

import typing
from typing import TypeVar, Generic, Tuple
from equivalib import MyType

S = TypeVar('S')
E = TypeVar('E')

class BoundedInt(Generic[S, E]):

    @staticmethod
    def unpack_type(base_type: MyType, args: Tuple[object, object]) -> Tuple[int, int]:
        assert len(args) == 2
        low_l, high_l = args
        low, high = (typing.get_args(low_l)[0], typing.get_args(high_l)[0])
        assert isinstance(low, int)
        assert isinstance(high, int)
        return (low, high)
