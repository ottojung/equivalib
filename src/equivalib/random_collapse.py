## Copyright (C) 2023  Otto Jung
## This program is free software: you can redistribute it and/or modify it under the terms of the GNU General Public License as published by the Free Software Foundation; version 3 of the License. This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more details. You should have received a copy of the GNU General Public License along with this program.  If not, see <http://www.gnu.org/licenses/>.

import random
from typing import Dict, Iterator, Union, Iterable, TYPE_CHECKING
from ortools.sat.python import cp_model

from equivalib.constant import Constant
from equivalib.generic_collapse import Collapser, generic_collapse
from equivalib.comparable import Comparable
from equivalib.sentence import Sentence
from equivalib.super import Super
from equivalib.structure import VarName


if TYPE_CHECKING:
    class _SolverCallbackBase:
        def __init__(self) -> None: ...

        def value(self, expression: object) -> int: ...
else:
    _SolverCallbackBase = cp_model.CpSolverSolutionCallback


class VarArraySolutionPrinter(_SolverCallbackBase):
    def __init__(self, variables):
        self._variables: Iterable[Comparable] = list(variables)
        self.collected: Dict[object, bool] = {}
        super().__init__()


    def on_solution_callback(self):
        mapped = tuple(self.value(v) for v in self._variables)
        self.collected[mapped] = True


    def get_collected(self) -> Iterator[Dict[str, Union[VarName, Constant]]]:
        for assignment in self.collected:
            yield {str(var): value for var, value in zip(self._variables, assignment)}  # type: ignore


class RandomCollapser(Collapser):
    def __init__(self, ctx: Sentence):
        solver = cp_model.CpSolver()
        variables = [v.get_var() for v in ctx.assignments.values() if isinstance(v, Super)]
        solution_printer = VarArraySolutionPrinter(variables)
        solver.parameters.enumerate_all_solutions = True
        solver.solve(ctx.model.model, solution_printer)
        assignments = tuple(solution_printer.get_collected())
        self.assignment = random.choice(assignments)


    def collapse(self, var: Comparable) -> Union[VarName, Constant]:
        return self.assignment[str(var)]


def random_collapse(self: Sentence) -> Sentence:
    return generic_collapse(self, RandomCollapser)
