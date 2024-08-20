## Copyright (C) 2023  Otto Jung
## This program is free software: you can redistribute it and/or modify it under the terms of the GNU General Public License as published by the Free Software Foundation; version 3 of the License. This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more details. You should have received a copy of the GNU General Public License along with this program.  If not, see <http://www.gnu.org/licenses/>.

from dataclasses import dataclass
from typing import Optional, Dict, Tuple
from ortools.sat.python import cp_model

from equivalib.mytype import MyType, MyGenType
from equivalib.comparable import Comparable
from equivalib.split_type import split_type
from equivalib.bounded_int import unpack_bounded_int


@dataclass
class SentenceModel:
    _model: Optional[cp_model.CpModel]
    _names: Dict[str, Tuple[MyType, int]]


    @staticmethod
    def empty() -> 'SentenceModel':
        return SentenceModel(None, {})


    def is_empty(self) -> bool:
        return len(self._names) == 0


    def copy(self) -> 'SentenceModel':
        if self._model is None:
            return SentenceModel.empty()
        else:
            return SentenceModel(self._model.Clone(), self._names.copy())


    def add_variable(self, name: str, t: MyGenType) -> None:
        (base_type, _args, _annot) = split_type(t)

        if isinstance(base_type, type) and base_type == int:
            low, high = unpack_bounded_int(t)
            var = self.model.NewIntVar(low, high, name)
        if isinstance(base_type, type) and base_type == bool:
            var = self.model.NewBoolVar(name)
        else:
            raise ValueError(f"Impossible base type {repr(base_type)}.")

        var_index: int = var.Index()
        self._names[name] = (base_type, var_index)


    def get_variable(self, name: str) -> Comparable:
        (base_type, arg) = self._names[name]
        if base_type == int:
            ret1: cp_model.IntVar = self.model.GetIntVarFromProtoIndex(arg)
            return ret1
        elif base_type == bool:
            ret2: cp_model.BoolVarT = self.model.GetBoolVarFromProtoIndex(arg)
            return ret2
        else:
            return arg


    def get_super_type(self, name: str) -> MyType:
        (base_type, _arg) = self._names[name]
        return base_type


    def add(self, expr: object) -> None:
        self.model.Add(expr)


    def check_satisfiability(self) -> bool:
        solver = cp_model.CpSolver()
        status = solver.Solve(self.model)
        return status in (cp_model.OPTIMAL, cp_model.FEASIBLE)  # type: ignore


    @property
    def model(self):
        if self._model is None:
            self._model = cp_model.CpModel()

        return self._model
