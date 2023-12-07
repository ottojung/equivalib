
import typing
from typing import Type, TypeAlias, Iterable, Literal, TypeVar

MyType: TypeAlias = Type[object]

InstantiateT = TypeVar('InstantiateT')

def instantiate(t: Type[InstantiateT], arguments: Iterable[object]) -> InstantiateT:
    base = typing.get_origin(t)
    if base == Literal:
        return next(iter(arguments)) # type: ignore
    else:
        return t(*arguments)
