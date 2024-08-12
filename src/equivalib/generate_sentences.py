## Copyright (C) 2023  Otto Jung
## This program is free software: you can redistribute it and/or modify it under the terms of the GNU General Public License as published by the Free Software Foundation; version 3 of the License. This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more details. You should have received a copy of the GNU General Public License along with this program.  If not, see <http://www.gnu.org/licenses/>.

from typing import Iterable, List, Iterator

from equivalib.sentence import Sentence
from equivalib.generator_type import GeneratorType, MaxgreedyType, GreedyType, WideType, BackType
import equivalib.extend_sentence as extend


def generate_suffixes(t: GeneratorType, ret: List[Sentence]) -> Iterator[Sentence]:
    for prefix in ret:
        if isinstance(t, MaxgreedyType):
            yield from list(extend.extend_sentence_maxgreedily(prefix, t.x))
        elif isinstance(t, GreedyType):
            yield from list(extend.extend_sentence_greedily(prefix, t.x))
        elif isinstance(t, WideType):
            yield from list(extend.extend_sentence_1(prefix, t.x))
        elif isinstance(t, BackType):
            yield from list(extend.extend_sentence_backracking(prefix, t.x))
        else:
            yield from list(extend.extend_sentence(prefix, t))


def generate_sentences(types: Iterable[GeneratorType], prefix: Sentence = Sentence.empty()) -> List[Sentence]:
    ret = [prefix]
    for t in types:
        ret = list(generate_suffixes(t, ret))
    return [x for x in ret if x.assignments]
