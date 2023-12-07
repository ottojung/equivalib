## Copyright (C) 2023  Otto Jung
## This program is free software: you can redistribute it and/or modify it under the terms of the GNU General Public License as published by the Free Software Foundation; version 3 of the License. This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more details. You should have received a copy of the GNU General Public License along with this program.  If not, see <http://www.gnu.org/licenses/>.

import random
from typing import Protocol
from equivalib import Super, Sentence, denv, Link, Constant, MyType, Comparable


class Collapser(Protocol):
    # pylint: disable=multiple-statements
    def __init__(self, ctx: Sentence) -> None: pass
    def collapse(self, var: Comparable) -> object: pass


def generic_collapse(self: Sentence, coll_t: type[Collapser]) -> Sentence:
    struct = self.structure.copy()

    with denv.let(sentence = self):
        coll = coll_t(self)
        for k, v in self.assignments.items():
            if isinstance(v, Super):
                var = v.get_var()
                if isinstance(var, list):
                    ty: MyType = Link
                    chosen_name, chosen_value = random.choice(var)
                    val = chosen_name or Constant(chosen_value)
                else:
                    val = coll.collapse(var)
                    ty = self.model.get_super_type(v.name)
                struct[k] = (ty, tuple([val]))

    return Sentence.from_structure(struct)
