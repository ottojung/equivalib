## Copyright (C) 2023  Otto Jung
## This program is free software: you can redistribute it and/or modify it under the terms of the GNU General Public License as published by the Free Software Foundation; version 3 of the License. This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more details. You should have received a copy of the GNU General Public License along with this program.  If not, see <http://www.gnu.org/licenses/>.

from dataclasses import dataclass
from typing import Generic, Tuple, Sequence, TypeVar
import equivalib
from equivalib import MyType


W = TypeVar('W')
@dataclass(frozen=True)
class Super(Generic[W]):
    name: str


    @staticmethod
    def make(t: MyType, arg: Sequence[object]) -> 'Super[W]':
        current_sentence = equivalib.get_current_sentence()
        name = current_sentence.add_super_variable(t, arg)
        ret: Super[W] = Super(name)
        struct = (Super, tuple([name]))
        current_sentence.insert_new_value(name, ret, struct)
        return ret


    def get_var(self: 'Super[W]') -> equivalib.Comparable:
        current_sentence = equivalib.get_current_sentence()
        current_model = current_sentence.model
        var = current_model.get_variable(self.name)
        return var


    def to_left_right(self, other: object) -> Tuple[equivalib.SentenceModel, equivalib.Comparable, equivalib.Comparable]:
        current_sentence = equivalib.get_current_sentence()
        current_model = current_sentence.model
        left = current_model.get_variable(self.name)

        if not isinstance(other, (Super, int, bool)):
            raise ValueError("Only support ints, bools and supervalues")

        if isinstance(other, Super):
            right = other.get_var()
        elif isinstance(other, (int, bool)):
            right = other

        return (current_model, left, right)


    def __lt__(self, other: object) -> bool:
        model, left, right = self.to_left_right(other)
        model.add(left < right)
        return model.check_satisfiability()


    def __gt__(self, other: object) -> bool:
        model, left, right = self.to_left_right(other)
        model.add(left > right)
        return model.check_satisfiability()


    def __le__(self, other: object) -> bool:
        model, left, right = self.to_left_right(other)
        model.add(left <= right)
        return model.check_satisfiability()


    def __ge__(self, other: object) -> bool:
        model, left, right = self.to_left_right(other)
        model.add(left >= right)
        return model.check_satisfiability()


    def __eq__(self, other: object) -> bool:
        model, left, right = self.to_left_right(other)
        model.add(left == right)
        return model.check_satisfiability()


    def __ne__(self, other: object) -> bool:
        model, left, right = self.to_left_right(other)
        model.add(left != right)
        return model.check_satisfiability()
