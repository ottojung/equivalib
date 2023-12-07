## Copyright (C) 2023  Otto Jung
## This program is free software: you can redistribute it and/or modify it under the terms of the GNU General Public License as published by the Free Software Foundation; version 3 of the License. This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more details. You should have received a copy of the GNU General Public License along with this program.  If not, see <http://www.gnu.org/licenses/>.

import random
from typing import Dict, Generator
from ortools.sat.python import cp_model
import equivalib
from equivalib import Collapser, Sentence, Comparable, Super


class VarArraySolutionPrinter(cp_model.CpSolverSolutionCallback): # type: ignore[misc]
    def __init__(self, variables):
        self._variables = variables
        self.collected = set()
        super().__init__()


    def on_solution_callback(self):
        mapped = tuple(self.Value(v) for v in self._variables)
        self.collected.add(mapped)


    def get_collected(self) -> Generator[Dict[str, object], None, None]:
        for assignment in self.collected:
            yield {str(var): value for var, value in zip(self._variables, assignment)}


class RandomCollapser(Collapser):
    def __init__(self, ctx: Sentence):
        solver = cp_model.CpSolver()
        variables = [v.get_var() for v in ctx.assignments.values() if isinstance(v, Super)]
        solution_printer = VarArraySolutionPrinter(variables)
        solver.parameters.enumerate_all_solutions = True
        solver.Solve(ctx.model.model, solution_printer)
        assignments = tuple(solution_printer.get_collected())
        self.assignment = random.choice(assignments)


    def collapse(self, var: Comparable) -> object:
        return self.assignment[str(var)]


def random_collapse(self: Sentence) -> Sentence:
    return equivalib.generic_collapse(self, RandomCollapser)
