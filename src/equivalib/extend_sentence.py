## Copyright (C) 2023  Otto Jung
## This program is free software: you can redistribute it and/or modify it under the terms of the GNU General Public License as published by the Free Software Foundation; version 3 of the License. This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more details. You should have received a copy of the GNU General Public License along with this program.  If not, see <http://www.gnu.org/licenses/>.

from typing import Union, Iterator, NoReturn
import itertools

from equivalib.dynamic import denv
from equivalib.constant import Constant
from equivalib.labelled_type import LabelledType
from equivalib.instantiate import instantiate
from equivalib.super import Super
from equivalib.sentence import Sentence
from equivalib.structure import Structure, VarName
from equivalib.fieldvalue import SFieldT, GFieldT

import equivalib.labelled_type as LT


def retreive_from_cache(ctx: Sentence, t: LabelledType) -> Iterator[VarName]:
    if isinstance(t, LT.UnionType):
        for arg in t.over:
            yield from retreive_from_cache(ctx, arg)
    else:
        yield from ctx.cache[t]


# pylint: disable=too-many-branches
def generate_field_values(ctx: Sentence, t: LabelledType) -> Iterator[GFieldT]:
    if isinstance(t, LT.SuperType):
        yield t

    elif ctx.has_cached(t):
        yield from retreive_from_cache(ctx, t)
        return

    elif isinstance(t, LT.BoolType):
        yield Structure(bool, t, (Constant(False), ))
        yield Structure(bool, t, (Constant(True), ))

    elif isinstance(t, LT.LiteralType):
        literal_value = t.value
        yield Structure(type(literal_value), t, arguments=(Constant(literal_value), ))

    elif isinstance(t, LT.UnionType):
        for arg in t.over:
            yield from generate_field_values(ctx, arg)

    elif isinstance(t, LT.TupleType):
        pointwise = []
        for arg in t.over:
            pointwise.append(tuple(retreive_from_cache(ctx, arg)))

        for prod in itertools.product(*pointwise):
            yield Structure(tuple, t, tuple(prod))

    elif isinstance(t, LT.BoundedIntType):
        low, high = (t.lo, t.hi)
        for i in range(low, high + 1):
            yield Structure(int, t, (Constant(i), ))

    elif isinstance(t, LT.DataclassType):
        pointwise = []

        for type_signature in t.fields:
            pointwise.append(tuple(retreive_from_cache(ctx, type_signature)))

        for prod in itertools.product(*pointwise):
            yield Structure(t.constructor, t, tuple(prod))

    else:
        _x: NoReturn = t
        raise ValueError(f"Cannot generate values of type {repr(t)}.")


def generate_instances_fields(ctx: Sentence, t: LabelledType) -> Iterator[GFieldT]:
    yield from generate_field_values(ctx, t)


def add_instance_nosuper(ctx: Sentence, t: LabelledType, handled: SFieldT) -> None:
    def loop2(handled: Union[SFieldT, Constant]) -> object:
        if isinstance(handled, Constant):
            return handled.value
        else:
            return loop(handled)

    def loop(handled: SFieldT) -> object:
        if isinstance(handled, LT.SuperType):
            name = ctx.add_super_variable(handled)
            return Super(name)
        elif isinstance(handled, Structure):
            args = [loop2(x) for x in handled.arguments]
            return instantiate(handled.constructor, handled.signature, args)
        elif isinstance(handled, str):
            return ctx.assignments[handled]
        else:
            _x: NoReturn = handled
            raise ValueError(f"Unexpected type {repr(handled)}.")

    instance = loop(handled)

    if isinstance(handled, Structure):
        struct = handled
    elif isinstance(handled, LT.SuperType):
        struct = Structure(LT.SuperType, t, tuple([]))
    elif isinstance(handled, str):
        struct = ctx.structure[handled]
    else:
        _x: NoReturn = handled
        raise ValueError(f"Unexpected type {repr(handled)}.")

    ctx.insert_value(instance, struct)


def add_instance(ctx: Sentence, t: LabelledType, value: GFieldT) -> bool:
    with denv.let(sentence = ctx):
        try:
            nosuper: SFieldT = value  # type: ignore
            add_instance_nosuper(ctx, t, nosuper)
        except AssertionError:
            return False
    return True

def extend_sentence(ctx: Sentence, t: LabelledType) -> Iterator[Sentence]:
    inputs = generate_instances_fields(ctx, t)
    is_based_on_super = not ctx.model.is_empty()

    ctx.last = []
    ret = ctx

    for inp in inputs:
        if is_based_on_super:
            ret = ctx.copy()

        if add_instance(ret, t, inp):
            if is_based_on_super:
                yield ret

    if not is_based_on_super:
        yield ret
