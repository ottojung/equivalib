## Copyright (C) 2023  Otto Jung
## This program is free software: you can redistribute it and/or modify it under the terms of the GNU General Public License as published by the Free Software Foundation; version 3 of the License. This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more details. You should have received a copy of the GNU General Public License along with this program.  If not, see <http://www.gnu.org/licenses/>.

from typing import Iterator
from equivalib.sentence import Sentence
from equivalib.mytype import MyType
from equivalib.get_types_hierarchy import get_types_hierarchy
from equivalib.generator_type import MaxgreedyType, WideType
from equivalib.mark_instance import mark_instance
from equivalib.arbitrary_collapse import arbitrary_collapse
from equivalib.generate_sentences import generate_sentences


def generate_instances(t: MyType, prefix: Sentence = Sentence.empty()) -> Iterator[object]:
    hierarchy = list(get_types_hierarchy([t]))
    flatten = [typ for types in hierarchy for typ in types]
    mapped = tuple(map(MaxgreedyType, flatten[:-1])) + tuple([WideType(flatten[-1])])
    yield from map(mark_instance, map(arbitrary_collapse , generate_sentences(mapped, prefix=prefix)))
