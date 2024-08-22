## Copyright (C) 2023  Otto Jung
## This program is free software: you can redistribute it and/or modify it under the terms of the GNU General Public License as published by the Free Software Foundation; version 3 of the License. This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more details. You should have received a copy of the GNU General Public License along with this program.  If not, see <http://www.gnu.org/licenses/>.

import random
from typing import Protocol, Union, NoReturn

from equivalib.dynamic import denv
from equivalib.constant import Constant
from equivalib.link import Link
from equivalib.typeform import TypeForm
from equivalib.comparable import Comparable
from equivalib.super import Super
from equivalib.sentence import Sentence
from equivalib.structure import Structure, VarName

import equivalib.labelled_type as LT


class Collapser(Protocol):
    # pylint: disable=multiple-statements
    def __init__(self, ctx: Sentence) -> None: pass
    def collapse(self, var: Comparable) -> Union[VarName, Constant]: pass


def generic_collapse(self: Sentence, coll_t: type[Collapser]) -> Sentence:
    struct = self.structure.copy()
    last_names = set(self.last)

    with denv.let(sentence = self):
        coll = coll_t(self)
        for k, v in self.assignments.items():
            if isinstance(v, Super):
                var = v.get_var()

                if isinstance(var, list):
                    ty: TypeForm = Link
                    chosen_name, chosen_value = random.choice(var)
                    val: Union[VarName, Constant] = chosen_name or Constant(chosen_value)
                else:
                    val = coll.collapse(var)
                    ty = self.model.get_super_type(v.name)

                if isinstance(ty.over, LT.BoolType):
                    constructor: Union[type[bool], type[int]] = bool
                elif isinstance(ty.over, LT.BoundedIntType):
                    constructor = int
                else:
                    _x: NoReturn = ty.over
                    raise ValueError(f"Impossible base type {repr(ty)}.")

                struct[k] = Structure(constructor, ty.over, tuple([val]))

    return Sentence.from_structure(struct, last_names)
