## Copyright (C) 2023  Otto Jung
## This program is free software: you can redistribute it and/or modify it under the terms of the GNU General Public License as published by the Free Software Foundation; version 3 of the License. This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more details. You should have received a copy of the GNU General Public License along with this program.  If not, see <http://www.gnu.org/licenses/>.

from ortools.sat.python import cp_model

from equivalib.constant import Constant
from equivalib.generic_collapse import Collapser, generic_collapse
from equivalib.comparable import Comparable
from equivalib.sentence import Sentence


class ArbitraryCollapser(Collapser):
    def __init__(self, ctx: Sentence):
        self.solver = cp_model.CpSolver()
        self.solver.solve(ctx.model.model)

    def collapse(self, var: Comparable) -> Constant:
        return Constant(self.solver.value(var))


def arbitrary_collapse(self: Sentence) -> Sentence:
    return generic_collapse(self, ArbitraryCollapser)
