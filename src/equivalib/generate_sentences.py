## Copyright (C) 2023  Otto Jung
## This program is free software: you can redistribute it and/or modify it under the terms of the GNU General Public License as published by the Free Software Foundation; version 3 of the License. This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more details. You should have received a copy of the GNU General Public License along with this program.  If not, see <http://www.gnu.org/licenses/>.

from typing import Iterable, Type, List, Generator
from equivalib import Sentence
import equivalib


def generate_suffixes(t: Type, ret: List[Sentence]) -> Generator[Sentence, None, None]:
    for prefix in ret:
        yield from list(equivalib.extend_sentence(prefix, t))


def generate_sentences(types: Iterable[Type]) -> List[Sentence]:
    ret = [Sentence.empty()]
    for t in types:
        ret = list(generate_suffixes(t, ret))
    return ret