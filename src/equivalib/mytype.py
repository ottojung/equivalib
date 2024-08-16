
import typing
from typing import Type, TypeAlias, Iterable, Literal, TypeVar, Union

from equivalib.bounded_int import BoundedInt

MyType: TypeAlias = Type[object]
MyGenType: TypeAlias = Union[MyType, object]

InstantiateT = TypeVar('InstantiateT')

def instantiate(t: Type[InstantiateT], sig: MyGenType, arguments: Iterable[object]) -> InstantiateT:
    base = typing.get_origin(sig) or sig
    if base == Literal:
        return next(iter(arguments))  # type: ignore
    elif base == BoundedInt:
        return int(*arguments)  # type: ignore
    elif base == tuple:
        return tuple(arguments)  # type: ignore
    elif base == set:
        return set(arguments)  # type: ignore
    else:
        return t(*arguments)
