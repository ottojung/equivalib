## Copyright (C) 2023  Otto Jung
## This program is free software: you can redistribute it and/or modify it under the terms of the GNU General Public License as published by the Free Software Foundation; version 3 of the License. This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more details. You should have received a copy of the GNU General Public License along with this program.  If not, see <http://www.gnu.org/licenses/>.

from dataclasses import is_dataclass
from typing import Tuple, Literal, Union, Iterator
import itertools

from equivalib.dynamic import denv
from equivalib.constant import Constant
from equivalib.mytype import MyGenType
from equivalib.instantiate import instantiate
from equivalib.super import Super
from equivalib.sentence import Sentence
from equivalib.structure import Structure, VarName
from equivalib.fieldvalue import Supertype, SFieldT, GFieldT
from equivalib.read_type_information import read_type_information
from equivalib.split_type import split_type
from equivalib.bounded_int import unpack_bounded_int


def retreive_from_cache(ctx: Sentence, t: MyGenType) -> Iterator[VarName]:
    (base_type, args, _annot) = split_type(t)

    if base_type == Union:
        for arg in args:
            yield from retreive_from_cache(ctx, arg)
    else:
        yield from ctx.cache[t]


# pylint: disable=too-many-branches
def generate_field_values(ctx: Sentence, t: MyGenType) -> Iterator[GFieldT]:
    (base_type, args, annot) = split_type(t)

    is_super = Super in annot

    if is_super:
        yield Supertype(t)

    elif ctx.has_cached(t):
        yield from retreive_from_cache(ctx, t)
        return

    elif base_type == bool:
        assert len(args) == 0
        yield Structure(bool, t, (Constant(False), ))
        yield Structure(bool, t, (Constant(True), ))

    elif base_type == Literal:
        assert len(args) == 1
        yield Structure(type(args[0]), t, arguments=(Constant(args[0]),))

    elif base_type == Union:
        assert len(args) > 0
        for arg in args:
            yield from generate_field_values(ctx, arg)

    elif base_type in (tuple, Tuple):
        assert len(args) > 0
        pointwise = []
        for arg in args:
            pointwise.append(tuple(retreive_from_cache(ctx, arg)))

        for prod in itertools.product(*pointwise):
            yield Structure(tuple, t, tuple(prod))

    elif base_type == int:
        low, high = unpack_bounded_int(t)
        for i in range(low, high + 1):
            yield Structure(int, t, (Constant(i), ))

    elif isinstance(t, type) and is_dataclass(t):
        information = read_type_information(t)
        pointwise = []

        for type_signature in information.values():
            # FIXME: handle supers.
            pointwise.append(tuple(retreive_from_cache(ctx, type_signature)))

        for prod in itertools.product(*pointwise):
            yield Structure(t, t, tuple(prod))

    else:
        raise ValueError(f"Cannot generate values of type {t!r}.")


def generate_instances_fields(ctx: Sentence, t: MyGenType) -> Iterator[GFieldT]:
    yield from generate_field_values(ctx, t)


def handle_supers(ctx: Sentence, value: GFieldT) -> SFieldT:
    if isinstance(value, Supertype):
        parameter = value.t
        (parameter_base, _parameter_args, _parameter_annotations) = split_type(parameter)
        if parameter_base not in (int, bool):
            raise ValueError("Can only have super of bool or bounded integer.")

        s: Super[object] = Super.make(parameter)
        return Structure(Super, Super[object], (Constant(s), ))
    else:
        return value


def add_instance_nosuper(ctx: Sentence, t: MyGenType, handled: SFieldT) -> None:
    def loop2(handled: Union[SFieldT, Constant]) -> object:
        if isinstance(handled, Constant):
            return handled.value
        else:
            return loop(handled)

    def loop(handled: SFieldT) -> object:
        if isinstance(handled, Structure):
            args = [loop2(x) for x in handled.arguments]
            return instantiate(handled.constructor, handled.signature, args)
        else:
            return ctx.assignments[handled]

    instance = loop(handled)

    if isinstance(handled, Structure):
        struct = handled
    else:
        struct = ctx.structure[handled]

    ctx.insert_value(instance, struct)


def add_instance(ctx: Sentence, t: MyGenType, value: GFieldT) -> bool:
    with denv.let(sentence = ctx):
        try:
            handled = handle_supers(ctx, value)
            add_instance_nosuper(ctx, t, handled)
        except AssertionError:
            return False
    return True

def extend_sentence(ctx: Sentence, t: MyGenType) -> Iterator[Sentence]:
    inputs = generate_instances_fields(ctx, t)

    ctx.last = []
    for inp in inputs:
        add_instance(ctx, t, inp)

    yield ctx
