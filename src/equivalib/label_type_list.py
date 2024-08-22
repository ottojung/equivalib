
from dataclasses import is_dataclass
from typing import Iterable, Iterator, Union, Tuple, Sequence, Literal, Dict

from equivalib.typeform import TypeForm
from equivalib.split_type import split_type
from equivalib.value_range import ValueRange
from equivalib.super import Super
from equivalib.read_type_information import read_type_information

import equivalib.labelled_type as LT


def label_bool_type() -> LT.BoolType:
    return LT.BoolType()


def label_int_type(annot: Iterable[TypeForm]) -> LT.BoundedIntType:
    if not annot:
        raise ValueError("Can only generate annotated integers like `Annotated[int, ValueRange(3, 9)]`.")

    value_range_list: Tuple[ValueRange, ...] = tuple(x for x in annot if isinstance(x, ValueRange))
    if not value_range_list:
        raise ValueError("Can only generate integers annotated with ValueRange, like `Annotated[int, ValueRange(3, 9)]`.")
    if len(value_range_list) > 1:
        raise ValueError("Multiple ValueRange annotations for int is not allowed..")

    return LT.BoundedIntType(range=value_range_list[0])


def label_literal_type(args: Sequence[TypeForm]) -> LT.LiteralType:
    if len(args) != 1:
        raise ValueError("Only single argument `Literal` types can be generated. Use `Union` for more arguments.")

    arg = args[0]
    if isinstance(arg, (bool, int, str)):
        return LT.LiteralType(arg)

    raise ValueError("Only literals of type `bool`, `int` and `str` can be generated.")


def label_dataclass_type(t: TypeForm, base_type: type[object], args: Sequence[TypeForm]) -> LT.DataclassType:
    if len(args) != 0:
        raise ValueError(f"Cannot generate generic dataclasses such as {repr(t)}.")

    fields_dict: Dict[str, LT.LabelledType] = {}

    free_fields = read_type_information(base_type)
    for name, ty in free_fields.items():
        fields_dict[name] = label_type(ty)

    fields = tuple(fields_dict.values())

    return LT.DataclassType(constructor=base_type, fields=fields)


# pylint: disable=too-many-return-statements
def label_type(t: TypeForm) -> LT.LabelledType:
    (base_type, args, annot) = split_type(t)

    if Super in annot:
        if base_type == int:
            super_over: Union[LT.BoundedIntType, LT.BoolType] = label_int_type(annot)
        elif base_type == bool:
            super_over = label_bool_type()
        else:
            raise ValueError(f"Cannot generate super values of base type {repr(base_type)}.")

        return LT.SuperType(super_over)

    if base_type == Literal:
        return label_literal_type(args)

    if base_type == Union:
        union_over = tuple(label_type(x) for x in args)
        return LT.UnionType(union_over)

    if base_type in (tuple, Tuple):
        tuple_over = tuple(label_type(x) for x in args)
        return LT.TupleType(tuple_over)

    if isinstance(base_type, type):
        if base_type == int:
            return label_int_type(annot)
        if base_type == bool:
            return label_bool_type()
        if is_dataclass(base_type):
            return label_dataclass_type(t, base_type, args)

        raise ValueError(f"Cannot generate values of base type {repr(base_type)}.")

    raise ValueError(f"Cannot generate values of type form {repr(t)}.")


def label_type_list(types: Iterable[TypeForm]) -> Iterator[LT.LabelledType]:
    for t in types:
        yield label_type(t)
