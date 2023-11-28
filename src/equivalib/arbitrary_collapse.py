## Copyright (C) 2023  Otto Jung
## This program is free software: you can redistribute it and/or modify it under the terms of the GNU General Public License as published by the Free Software Foundation; version 3 of the License. This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more details. You should have received a copy of the GNU General Public License along with this program.  If not, see <http://www.gnu.org/licenses/>.

from copy import deepcopy
import dataclasses
import typing
from ortools.sat.python import cp_model
from equivalib import Super, Sentence, denv, Dict, Any

def set_int_fields_to_value(instance, lookup):
    instance = deepcopy(instance)
    for field in dataclasses.fields(instance):
        t = field.type
        base_type = typing.get_origin(t) or t
        if base_type == Super:
            value = lookup[getattr(instance, field.name).name]
            setattr(instance, field.name, value)
    return instance


def arbitrary_collapse(self: Sentence) -> Sentence:
    ret = Sentence.empty()

    solver = cp_model.CpSolver()
    solver.Solve(self.model.model)
    supers: Dict[str, Any] = {}

    with denv.let(sentence = self):
        for k, v in self.assignments.items():
            assert isinstance(v, Super) or dataclasses.is_dataclass(v)
            if isinstance(v, Super):
                var = v.get_var()
                val = solver.Value(var)
                supers[k] = val
            elif dataclasses.is_dataclass(v):
                ret.assignments[k] = set_int_fields_to_value(v, supers)

    return ret
