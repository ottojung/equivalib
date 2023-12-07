
import typing
from typing import Type, TypeAlias, Iterable, Literal

MyType: TypeAlias = Type[object]

def instantiate(t: MyType, arguments: Iterable[object]) -> object:
    base = typing.get_origin(t)
    if base == Literal:
        return next(iter(arguments))
    else:
        return t(*arguments)
