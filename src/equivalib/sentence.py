## Copyright (C) 2023  Otto Jung
## This program is free software: you can redistribute it and/or modify it under the terms of the GNU General Public License as published by the Free Software Foundation; version 3 of the License. This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more details. You should have received a copy of the GNU General Public License along with this program.  If not, see <http://www.gnu.org/licenses/>.

import typing
from typing import Dict, List, Tuple, Literal, Set
from dataclasses import dataclass

from equivalib.sentence_model import SentenceModel
from equivalib.dynamic import denv
from equivalib.constant import Constant
from equivalib.link import Link
from equivalib.mytype import MyGenType, instantiate
from equivalib.bounded_int import BoundedInt
from equivalib.structure import Structure, VarName


@dataclass
class Sentence:
    assignments: Dict[VarName, object]
    structure: Dict[VarName, Structure]
    reverse: Dict[Structure, VarName]
    cache: Dict[MyGenType, List[VarName]]
    last: List[VarName]
    model: SentenceModel


    @staticmethod
    def empty() -> 'Sentence':
        return Sentence({}, {}, {}, {}, [], SentenceModel.empty())


    # def __copy__(self) -> 'Sentence':
    #     # Note: cache is SHARED among all copies.
    #     return Sentence(self.assignments.copy(), self.structure.copy(), self.reverse.copy(), self.cache, self.last, self.model.copy())


    # def copy(self) -> 'Sentence':
    #     return self.__copy__()


    def has_cached(self, typ: MyGenType) -> bool:
        return typ in self.cache


    def insert_new_value(self, name: VarName, value: object, struct: Structure) -> None:
        self.assignments[name] = value
        self.structure[name] = struct
        if struct in self.reverse:
            raise ValueError(f"Struct {repr(struct)} is already in the Sentence.")

        self.reverse[struct] = name
        sig = struct.signature
        if sig in self.cache:
            self.cache[sig].append(VarName(name))
        else:
            self.cache[sig] = [VarName(name)]

        self.last.append(name)


    def insert_value(self, value: object, struct: Structure) -> str:
        if struct in self.reverse:
            name = self.reverse[struct]
            self.last.append(name)
            return name
        else:
            name = self.generate_free_name()
            self.reverse[struct] = name
            self.assignments[name] = value
            self.structure[name] = struct

            sig = struct.signature
            if sig in self.cache:
                self.cache[sig].append(VarName(name))
            else:
                self.cache[sig] = [VarName(name)]

            self.last.append(name)

            return name


    def add_super_variable(self, t: MyGenType) -> VarName:
        name = self.generate_free_name()
        self.model.add_variable(name, t)
        return name


    def generate_free_name(self) -> VarName:
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

        return VarName(candidate)


    @staticmethod
    def from_structure(structure: Dict[VarName, Structure], last_names: Set[VarName]) -> 'Sentence':
        ret = Sentence.empty()
        ret.structure = structure

        def unwrap(arg: object) -> object:
            if isinstance(arg, str):
                return get(VarName(arg))
            elif isinstance(arg, Constant):
                return arg.value
            else:
                return arg

        def get(name: VarName) -> object:
            if name not in ret.assignments:
                struct = structure[name]
                ty = struct.constructor
                sig = struct.signature
                args_names = struct.arguments
                args = [unwrap(name) for name in args_names]
                instance = instantiate(ty, sig, args)
                ret.insert_new_value(name, instance, struct)

            val = ret.assignments[name]
            while isinstance(val, Constant):
                val = val.value
            return val

        with denv.let(sentence = ret):
            for key in structure:
                get(key)

        ret.last = [x for x in ret.last if x in last_names]

        return ret


    def __str__(self) -> str:
        assignments = []

        def sortkey(p: Tuple[str, object]) -> Tuple[int, str]:
            k, _v = p
            return (len(k), k)

        def unwrap(x: object) -> object:
            if isinstance(x, Constant):
                return unwrap(x.value)
            else:
                return x

        for k, v in sorted(self.structure.items(), key=sortkey):
            ty = v.constructor
            args_names = v.arguments
            base_type = typing.get_origin(ty) or ty
            if base_type in (bool, int, Link, BoundedInt, Literal):
                args_values = list(map(unwrap, args_names))
                value = repr(instantiate(ty, v.signature, args_values))
            else:
                args = ', '.join(map(str, args_names))
                typename = '' if base_type == tuple else ty.__name__
                value = f"{typename}({args})"
            a = f"{k} = {value}"
            assignments.append(a)

        return '; '.join(assignments) + ';'
