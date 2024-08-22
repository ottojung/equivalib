
from typing import Type, TypeVar, Iterable, NoReturn

import equivalib.labelled_type as LT

InstantiateT = TypeVar('InstantiateT')

def instantiate(t: Type[InstantiateT], sig: LT.LabelledType, arguments: Iterable[object]) -> InstantiateT:
    if isinstance(sig, LT.LiteralType):
        return next(iter(arguments))  # type: ignore
    elif isinstance(sig, LT.BoolType):
        return next(iter(arguments))  # type: ignore
    elif isinstance(sig, LT.BoundedIntType):
        return next(iter(arguments))  # type: ignore
    elif isinstance(sig, LT.TupleType):
        return tuple(arguments)  # type: ignore
    elif isinstance(sig, LT.UnionType):
        raise ValueError("Should not instantiate union type.")
    elif isinstance(sig, LT.SuperType):
        raise ValueError(f"Should not instantiate super type {repr(sig)}. Have t = {repr(t)}.")
    elif isinstance(sig, LT.DataclassType):
        return sig.constructor(*arguments)  # type: ignore
    else:
        _x: NoReturn = sig
        raise TypeError(f"Unknown type {repr(sig)}.")
