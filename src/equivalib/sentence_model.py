## Copyright (C) 2023  Otto Jung
## This program is free software: you can redistribute it and/or modify it under the terms of the GNU General Public License as published by the Free Software Foundation; version 3 of the License. This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more details. You should have received a copy of the GNU General Public License along with this program.  If not, see <http://www.gnu.org/licenses/>.

from dataclasses import dataclass
import typing
from typing import Optional, Any, Dict, Type, Tuple
from ortools.sat.python import cp_model
from equivalib import BoundedInt

@dataclass
class SentenceModel:
    _model: Optional[cp_model.CpModel]
    _names: Dict[str, Tuple[int, Type]]


    @staticmethod
    def empty() -> 'SentenceModel':
        return SentenceModel(None, {})


    def copy(self) -> 'SentenceModel':
        if self._model is None:
            return SentenceModel.empty()
        else:
            return SentenceModel(self._model.Clone(), self._names.copy())


    def add_variable(self, name: str, t: Type):
        base_type = typing.get_origin(t) or t
        args = typing.get_args(t)

        # TODO: extend to dataclasses and Union's
        assert base_type in (BoundedInt, bool), f"Only bool and BoundedInt can have Super values, got {base_type!r}"
        if base_type == BoundedInt:
            low, high = BoundedInt.unpack_type(base_type, args)
            var = self.model.NewIntVar(low, high, name)
        elif base_type == bool:
            var = self.model.NewBoolVar(name)

        index = var.Index()
        self._names[name] = (index, base_type)


    def get_variable(self, name: str):
        (index, base_type) = self._names[name]
        assert base_type in (BoundedInt, bool)
        if base_type == BoundedInt:
            var = self.model.GetIntVarFromProtoIndex(index)
        elif base_type == bool:
            var = self.model.GetBoolVarFromProtoIndex(index)
        return var


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
