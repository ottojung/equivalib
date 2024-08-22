
from dataclasses import dataclass
from typing import Union, Tuple

from equivalib.value_range import ValueRange


@dataclass(frozen=True)
class BoolType:
    pass


@dataclass(frozen=True)
class LiteralType:
    value: Union[bool, int, str]


@dataclass(frozen=True)
class BoundedIntType:
    range: ValueRange


@dataclass(frozen=True)
class SuperType:
    over: Union[BoolType, BoundedIntType]


@dataclass(frozen=True)
class UnionType:
    over: Tuple['LabelledType', ...]


@dataclass(frozen=True)
class TupleType:
    over: Tuple['LabelledType', ...]


@dataclass(frozen=True)
class DataclassType:
    constructor: type[object]
    fields: Tuple['LabelledType', ...]


LabelledType = Union[BoolType, LiteralType, BoundedIntType, SuperType, UnionType, TupleType, DataclassType]
