## Copyright (C) 2023  Otto Jung
## This program is free software: you can redistribute it and/or modify it under the terms of the GNU General Public License as published by the Free Software Foundation; version 3 of the License. This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more details. You should have received a copy of the GNU General Public License along with this program.  If not, see <http://www.gnu.org/licenses/>.

from dataclasses import dataclass
import typing
from typing import Optional, Dict, Tuple, List, Union, Sequence
from ortools.sat.python import cp_model
from equivalib import BoundedInt, MyType

@dataclass
class SentenceModel:
    _model: Optional[cp_model.CpModel]
    _names: Dict[str, Tuple[MyType, Union[int, List[object]]]]


    @staticmethod
    def empty() -> 'SentenceModel':
        return SentenceModel(None, {})


    def copy(self) -> 'SentenceModel':
        if self._model is None:
            return SentenceModel.empty()
        else:
            return SentenceModel(self._model.Clone(), self._names.copy())


    def add_variable(self, name: str, t: MyType, arg: Sequence[object]):
        base_type = typing.get_origin(t) or t
        args = typing.get_args(t)

        if base_type == BoundedInt:
            low, high = BoundedInt.unpack_type(base_type, args)
            var = self.model.NewIntVar(low, high, name)
        elif base_type == bool:
            var = self.model.NewBoolVar(name)
        else:
            var = None

        vals = var.Index() if len(arg) == 0 else arg
        self._names[name] = (base_type, vals)


    def get_variable(self, name: str):
        (base_type, arg) = self._names[name]
        if base_type == BoundedInt:
            return self.model.GetIntVarFromProtoIndex(arg)
        elif base_type == bool:
            return self.model.GetBoolVarFromProtoIndex(arg)
        else:
            return arg


    def get_super_type(self, name: str) -> MyType:
        (base_type, _arg) = self._names[name]
        if base_type == BoundedInt:
            return int
        else:
            return base_type


    def add(self, expr: object):
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
