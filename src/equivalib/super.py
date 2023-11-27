## Copyright (C) 2023  Otto Jung
## This program is free software: you can redistribute it and/or modify it under the terms of the GNU General Public License as published by the Free Software Foundation; version 3 of the License. This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more details. You should have received a copy of the GNU General Public License along with this program.  If not, see <http://www.gnu.org/licenses/>.

from typing import TypeVar, Generic, Any, Tuple
import equivalib

W = TypeVar('W')

class Super(Generic[W]):
    def __init__(self: 'Super'):
        current_model = equivalib.get_current_model()
        var = current_model.model.NewIntVar(0, 10, 'x')
        self.index = var.index


    def get_var(self: 'Super'):
        model = equivalib.get_current_model()
        var = model.model.GetIntVarFromProtoIndex(self.index)
        return var


    def _to_left_right(self, other: Any) -> Tuple[equivalib.SentenceModel, Any, Any]:
        model = equivalib.get_current_model()
        left = model.model.GetIntVarFromProtoIndex(self.index)

        if isinstance(other, Super):
            right = other.get_var()
        elif isinstance(other, int):
            right = other
        else:
            raise ValueError("Only support ints and super ints")

        return (model, left, right)


    def __lt__(self, other: Any) -> bool:
        model, left, right = self._to_left_right(other)
        model.add(left < right)
        return model.check_satisfiability()


    def __gt__(self, other: Any) -> bool:
        model, left, right = self._to_left_right(other)
        model.add(left > right)
        return model.check_satisfiability()


    def __le__(self, other: Any) -> bool:
        model, left, right = self._to_left_right(other)
        model.add(left <= right)
        return model.check_satisfiability()


    def __ge__(self, other: Any) -> bool:
        model, left, right = self._to_left_right(other)
        model.add(left >= right)
        return model.check_satisfiability()


    def __eq__(self, other: Any) -> bool:
        model, left, right = self._to_left_right(other)
        model.add(left == right)
        return model.check_satisfiability()


    def __neq__(self, other: Any) -> bool:
        model, left, right = self._to_left_right(other)
        model.add(left != right)
        return model.check_satisfiability()
