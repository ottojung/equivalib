## Copyright (C) 2023  Otto Jung
## This program is free software: you can redistribute it and/or modify it under the terms of the GNU General Public License as published by the Free Software Foundation; version 3 of the License. This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more details. You should have received a copy of the GNU General Public License along with this program.  If not, see <http://www.gnu.org/licenses/>.

from typing import Any, Dict, Type, List, Tuple
from dataclasses import dataclass
from equivalib import SentenceModel

@dataclass
class Sentence:
    assignments: Dict[str, Any]
    structure: Dict[str, Tuple[Type, List[str]]]
    model: SentenceModel


    @staticmethod
    def empty() -> 'Sentence':
        return Sentence({}, {}, SentenceModel.empty())


    def copy(self) -> 'Sentence':
        return Sentence(self.assignments.copy(), self.structure.copy(), self.model.copy())


    def add_super_variable(self, t: Type) -> str:
        name = self.generate_free_name()
        self.model.add_variable(name, t)
        return name


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


    @staticmethod
    def from_structure(structure: Dict[str, Tuple[Type, List[str]]]) -> 'Sentence':
        ret = Sentence.empty()

        def get(name: str):
            if name not in ret.assignments:
                (ty, args_names) = structure[name]
                args = [get(name) if name in structure else name for name in args_names]
                ret.assignments[name] = ty(*args)

            return ret.assignments[name]

        for key in structure:
            get(key)

        return ret
