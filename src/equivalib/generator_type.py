## Copyright (C) 2023  Otto Jung
## This program is free software: you can redistribute it and/or modify it under the terms of the GNU General Public License as published by the Free Software Foundation; version 3 of the License. This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more details. You should have received a copy of the GNU General Public License along with this program.  If not, see <http://www.gnu.org/licenses/>.

from dataclasses import dataclass
from typing import Union
from equivalib import MyType


@dataclass(frozen=True)
class MaxgreedyType:
    x: MyType


@dataclass(frozen=True)
class GreedyType:
    x: MyType


@dataclass(frozen=True)
class WideType:
    x: MyType


@dataclass(frozen=True)
class BackType:
    x: MyType


GeneratorType = Union[MyType, GreedyType, MaxgreedyType, WideType, BackType]
