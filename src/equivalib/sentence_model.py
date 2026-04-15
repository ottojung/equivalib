## Copyright (C) 2023  Otto Jung
## This program is free software: you can redistribute it and/or modify it under the terms of the GNU General Public License as published by the Free Software Foundation; version 3 of the License. This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more details. You should have received a copy of the GNU General Public License along with this program.  If not, see <http://www.gnu.org/licenses/>.

from dataclasses import dataclass
from typing import Optional, Dict, Tuple, NoReturn, Union
from ortools.sat.python import cp_model
import numpy as np

from equivalib.comparable import Comparable

import equivalib.labelled_type as LT


@dataclass
class SentenceModel:
    _model: Optional[cp_model.CpModel]
    _names: Dict[str, Tuple[LT.SuperType, int]]


    @staticmethod
    def empty() -> 'SentenceModel':
        return SentenceModel(None, {})


    def is_empty(self) -> bool:
        return len(self._names) == 0


    def copy(self) -> 'SentenceModel':
        if self._model is None:
            return SentenceModel.empty()
        else:
            return SentenceModel(self._model.clone(), self._names.copy())


    def add_variable(self, name: str, t: LT.SuperType) -> None:
        if isinstance(t.over, LT.BoundedIntType):
            low, high = (t.over.range.min, t.over.range.max)
            var = self.model.new_int_var(low, high, name)
        elif isinstance(t.over, LT.BoolType):
            var = self.model.new_bool_var(name)
        else:
            _x: NoReturn = t.over
            raise ValueError(f"Impossible base type {repr(t)}.")

        var_index: int = var.index
        self._names[name] = (t, var_index)


    def get_variable(self, name: str) -> Comparable:
        (t, index) = self._names[name]

        if isinstance(t.over, LT.BoundedIntType):
            ret1: cp_model.IntVar = self.model.get_int_var_from_proto_index(index)
            return ret1

        if isinstance(t.over, LT.BoolType):
            ret2: cp_model.IntVar = self.model.get_bool_var_from_proto_index(index)
            return ret2

        _x: NoReturn = t.over
        raise ValueError(f"Impossible base type {repr(t)}.")


    def get_super_type(self, name: str) -> LT.SuperType:
        (t, _index) = self._names[name]
        return t


    def add(self, expr: Union[cp_model.BoundedLinearExpression, bool, np.bool_]) -> None:
        self.model.add(expr)


    def check_satisfiability(self) -> bool:
        solver = cp_model.CpSolver()
        status = solver.solve(self.model)
        return status in (cp_model.OPTIMAL, cp_model.FEASIBLE)


    @property
    def model(self) -> cp_model.CpModel:
        if self._model is None:
            self._model = cp_model.CpModel()

        return self._model
