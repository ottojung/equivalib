## Copyright (C) 2023  Otto Jung
## This program is free software: you can redistribute it and/or modify it under the terms of the GNU General Public License as published by the Free Software Foundation; version 3 of the License. This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more details. You should have received a copy of the GNU General Public License along with this program.  If not, see <http://www.gnu.org/licenses/>.

from typing import Any, Dict
from dataclasses import dataclass
from equivalib import SentenceModel

@dataclass
class GeneratorContext:
    assignments: Dict[str, Any]
    model: SentenceModel


    @staticmethod
    def empty() -> 'GeneratorContext':
        return GeneratorContext({}, SentenceModel.empty())


    def copy(self) -> 'GeneratorContext':
        return GeneratorContext(self.assignments.copy(), self.model.copy())


    def generate_free_name(self) -> str:
        """
        Returns the (lexicographically) smallest string
        that is not in self.assignments.
        """

        # An iterative approach, starts with 'a', 'b'...
        # if 'z' is reached, continues with 'aa', 'ab'... and so on.
        def next_alpha_name(s):
            if not s:
                return 'a'
            if s[-1] < 'z':
                return s[:-1] + chr(ord(s[-1]) + 1)
            return next_alpha_name(s[:-1]) + 'a'

        candidate = 'a'
        while candidate in self.assignments:
            candidate = next_alpha_name(candidate)

        return candidate
