## Copyright (C) 2023  Otto Jung
## This program is free software: you can redistribute it and/or modify it under the terms of the GNU General Public License as published by the Free Software Foundation; version 3 of the License. This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more details. You should have received a copy of the GNU General Public License along with this program.  If not, see <http://www.gnu.org/licenses/>.

from typing import Iterable, Type, List
from equivalib import GeneratorContext
import equivalib


def generate_suffixes(t: Type, ret: List[GeneratorContext]) -> Iterable[List[GeneratorContext]]:
    for prefix in ret:
        yield from equivalib.extend_context(prefix, t)


def extend_prefixes(t, ret: List[List[GeneratorContext]]) -> Iterable[List[GeneratorContext]]:
    for sentence in ret:
        yield from generate_suffixes(t, sentence)


def generate_context(types: Iterable[Type]) -> List[List[GeneratorContext]]:
    ret = [[GeneratorContext({})]]
    for t in types:
        ret = list(extend_prefixes(t, ret))
    return ret
