## Copyright (C) 2023  Otto Jung
## This program is free software: you can redistribute it and/or modify it under the terms of the GNU General Public License as published by the Free Software Foundation; version 3 of the License. This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more details. You should have received a copy of the GNU General Public License along with this program.  If not, see <http://www.gnu.org/licenses/>.

from typing import Optional, Any
from ortools.sat.python import cp_model

class SentenceModel:
    def __init__(self, model: Optional[cp_model.CpModel]):
        self._model = model


    @staticmethod
    def empty() -> 'SentenceModel':
        return SentenceModel(None)


    def copy(self) -> 'SentenceModel':
        if self.model is None:
            return SentenceModel.empty()
        else:
            return SentenceModel(self.model.Clone())


    def add(self, expr: Any):
        self.model.Add(expr)


    def check_satisfiability(self) -> bool:
        solver = cp_model.CpSolver()
        status = solver.Solve(self.model)
        return status in (cp_model.OPTIMAL, cp_model.FEASIBLE)


    @property
    def model(self):
        if self._model is None:
            self._model = cp_model.CpModel()

        return self._model
