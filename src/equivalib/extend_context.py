## Copyright (C) 2023  Otto Jung
## This program is free software: you can redistribute it and/or modify it under the terms of the GNU General Public License as published by the Free Software Foundation; version 3 of the License. This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more details. You should have received a copy of the GNU General Public License along with this program.  If not, see <http://www.gnu.org/licenses/>.

from typing import Type, Iterable, Optional
from ortools.sat.python import cp_model
import equivalib
from equivalib import GeneratorContext


def copy_model(model: Optional[cp_model.CpModel]) -> Optional[cp_model.CpModel]:
    if model is None:
        return None
    else:
        return model.Clone()


def extend_by_sentence(ctx, sentence) -> GeneratorContext:
    new = GeneratorContext(ctx.assignments.copy(), copy_model(ctx.model))
    for instance in sentence:
        name = new.generate_free_name()
        new.assignments[name] = instance
    return new


def extend_context(ctx: GeneratorContext, t: Type) -> Iterable[GeneratorContext]:
    sentences = equivalib.generate_instances(ctx, t)
    for sentence in sentences:
        yield extend_by_sentence(ctx, sentence)
