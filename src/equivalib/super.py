## Copyright (C) 2023  Otto Jung
## This program is free software: you can redistribute it and/or modify it under the terms of the GNU General Public License as published by the Free Software Foundation; version 3 of the License. This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more details. You should have received a copy of the GNU General Public License along with this program.  If not, see <http://www.gnu.org/licenses/>.

from dataclasses import dataclass
import typing
from typing import TypeVar, Generic, Any, Tuple
import equivalib
from equivalib import BoundedInt

W = TypeVar('W')

@dataclass(frozen=True)
class Super(Generic[W]):
    index: int


    @staticmethod
    def make(t):
        current_context = equivalib.get_current_context()
        current_model = current_context.model

        name = current_context.generate_free_name()

        base_type = typing.get_origin(t) or t
        args = typing.get_args(t)
        if base_type == BoundedInt:
            low, high = BoundedInt.unpack_type(base_type, args)
            var = current_model.model.NewIntVar(low, high, name)
        elif base_type == bool:
            var = current_model.model.NewBoolVar(name)
        else:
            # TODO: extend to dataclasses
            raise ValueError("Only bool and BoundedInt can have Super values")

        ret = Super(var.Index())
        current_context.assignments[name] = ret
        return ret


    def get_var(self: 'Super'):
        current_context = equivalib.get_current_context()
        current_model = current_context.model
        var = current_model.model.GetIntVarFromProtoIndex(self.index)
        return var


    def _to_left_right(self, other: Any) -> Tuple[equivalib.SentenceModel, Any, Any]:
        current_context = equivalib.get_current_context()
        current_model = current_context.model
        left = current_model.model.GetIntVarFromProtoIndex(self.index)

        if isinstance(other, Super):
            right = other.get_var()
        elif isinstance(other, int):
            right = other
        else:
            raise ValueError("Only support ints and super ints")

        return (current_model, left, right)


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
