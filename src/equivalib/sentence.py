## Copyright (C) 2023  Otto Jung
## This program is free software: you can redistribute it and/or modify it under the terms of the GNU General Public License as published by the Free Software Foundation; version 3 of the License. This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more details. You should have received a copy of the GNU General Public License along with this program.  If not, see <http://www.gnu.org/licenses/>.

from typing import Dict, List, Tuple, Union, Sequence, Optional
from dataclasses import dataclass
from equivalib import SentenceModel, denv, Constant, Link, MyType


Structure = Tuple[MyType, Tuple[Union[str, Constant], ...]]


@dataclass
class Sentence:
    assignments: Dict[str, object]
    last: Optional[object]
    structure: Dict[str, Structure]
    reverse: Dict[Structure, Union[str, List[str]]]
    model: SentenceModel


    @staticmethod
    def empty() -> 'Sentence':
        return Sentence({}, None, {}, {}, SentenceModel.empty())


    def copy(self) -> 'Sentence':
        return Sentence(self.assignments.copy(), self.last, self.structure.copy(), self.reverse.copy(), self.model.copy())


    def insert_new_value(self, name: str, value: object, struct: Structure) -> None:
        self.assignments[name] = value
        self.last = value
        self.structure[name] = struct
        if struct in self.reverse:
            existing = self.reverse[struct]
            if isinstance(existing, str):
                self.reverse[struct] = [existing, name]
            else:
                existing.append(name)
        else:
            self.reverse[struct] = name


    def insert_value(self, value: object, struct: Structure) -> str:
        if struct in self.reverse:
            existing = self.reverse[struct]
            if isinstance(existing, str):
                key = existing
            else:
                key = existing[0]
            self.last = self.assignments[key]
            return key
        else:
            name = self.generate_free_name()
            self.last = value
            self.reverse[struct] = name
            self.assignments[name] = value
            self.structure[name] = struct
            return name


    def add_super_variable(self, t: MyType, arg: Sequence[object]) -> str:
        name = self.generate_free_name()
        self.model.add_variable(name, t, arg)
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
    def from_structure(structure: Dict[str, Structure]) -> 'Sentence':
        ret = Sentence.empty()
        ret.structure = structure

        def get(name: str) -> object:
            if name not in ret.assignments:
                (ty, args_names) = structure[name]
                args = [get(name) if isinstance(name, str) else name for name in args_names]
                struct = (ty, args_names)
                ret.insert_new_value(name, ty(*args), struct)

            return ret.assignments[name]

        with denv.let(sentence = ret):
            for key in structure:
                get(key)

        return ret


    def __str__(self) -> str:
        assignments = []

        def sortkey(p: Tuple[str, object]) -> Tuple[int, str]:
            k, _v = p
            return (len(k), k)

        for k, v in sorted(self.structure.items(), key=sortkey):
            (ty, args_names) = v
            if ty in (bool, int, Link):
                value = repr(ty(args_names[0])) # type: ignore
            else:
                args = ', '.join(map(str, args_names))
                value = f"{ty.__name__}({args})"
            a = f"{k} = {value}"
            assignments.append(a)

        return '; '.join(assignments) + ';'
