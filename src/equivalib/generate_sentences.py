## Copyright (C) 2023  Otto Jung
## This program is free software: you can redistribute it and/or modify it under the terms of the GNU General Public License as published by the Free Software Foundation; version 3 of the License. This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more details. You should have received a copy of the GNU General Public License along with this program.  If not, see <http://www.gnu.org/licenses/>.

from typing import Iterable, Iterator, Optional, Sequence

from equivalib.sentence import Sentence
from equivalib.labelled_type import LabelledType
from equivalib.extend_sentence import extend_sentence


def generate_suffixes(t: LabelledType, ret: Iterable[Sentence]) -> Iterator[Sentence]:
    for prefix in ret:
        yield from list(extend_sentence(prefix, t))


def generate_sentences(types: Iterable[LabelledType], prefix: Optional[Sentence] = None) -> Sequence[Sentence]:

    if prefix is None:
        prefix = Sentence.empty()

    ret = [prefix]
    for t in types:
        ret = list(generate_suffixes(t, ret))

    return [x for x in ret if not x.is_empty()]
