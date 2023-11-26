## Copyright (C) 2023  Otto Jung
## This program is free software: you can redistribute it and/or modify it under the terms of the GNU General Public License as published by the Free Software Foundation; version 3 of the License. This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more details. You should have received a copy of the GNU General Public License along with this program.  If not, see <http://www.gnu.org/licenses/>.

from typing import Set, Type, Iterable, Generator
import equivalib

def get_types_hierarchy(types: Iterable[Type]) -> Generator[Set[Type], None, None]:
    before = {}
    for t in types:
        information = equivalib.read_type_information(t)
        before[t] = {values[0] for (field, values) in information.items()}

    return equivalib.partially_order(types, lambda t: before[t])
