## Copyright (C) 2023  Otto Jung
## This program is free software: you can redistribute it and/or modify it under the terms of the GNU General Public License as published by the Free Software Foundation; version 3 of the License. This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more details. You should have received a copy of the GNU General Public License along with this program.  If not, see <http://www.gnu.org/licenses/>.

from typing import Generator
import equivalib as eqv


def generate_instances(t: eqv.MyType, prefix: eqv.Sentence = eqv.Sentence.empty()) -> Generator[eqv.Sentence, None, None]:
    hierarchy = list(eqv.get_types_hierarchy([t]))
    flatten = [typ for types in hierarchy for typ in types]
    mapped = tuple(map(eqv.MaxgreedyType, flatten[:-1])) + tuple([eqv.WideType(flatten[-1])])
    yield from eqv.generate_sentences(mapped, prefix=prefix)
