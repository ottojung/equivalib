## Copyright (C) 2023  Otto Jung
## This program is free software: you can redistribute it and/or modify it under the terms of the GNU General Public License as published by the Free Software Foundation; version 3 of the License. This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more details. You should have received a copy of the GNU General Public License along with this program.  If not, see <http://www.gnu.org/licenses/>.

from ortools.sat.python import cp_model
from equivalib import Super, Sentence, denv


def arbitrary_collapse(self: Sentence) -> Sentence:
    struct = self.structure.copy()

    solver = cp_model.CpSolver()
    solver.Solve(self.model.model)

    with denv.let(sentence = self):
        for k, v in self.assignments.items():
            if isinstance(v, Super):
                var = v.get_var()
                val = solver.Value(var)
                ty = self.model.get_super_type(v.name)
                struct[k] = (ty, [val])

    return Sentence.from_structure(struct)
