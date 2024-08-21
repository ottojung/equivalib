
from typing import Type, TypeVar, Iterable, Literal

from equivalib.typeform import TypeForm
from equivalib.supertype import Supertype
from equivalib.split_type import split_type

InstantiateT = TypeVar('InstantiateT')

def instantiate(t: Type[InstantiateT], sig: TypeForm, arguments: Iterable[object]) -> InstantiateT:
    (base, _args, _annot) = split_type(sig)
    if base == Literal:
        return next(iter(arguments))  # type: ignore
    elif base == int:
        return int(*arguments)  # type: ignore
    elif base == tuple:
        return tuple(arguments)  # type: ignore
    elif base == set:
        return set(arguments)  # type: ignore
    elif base == Supertype:
        raise ValueError("Should not instantiate supertype.")
    else:
        return t(*arguments)
