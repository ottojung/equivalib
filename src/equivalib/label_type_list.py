
from dataclasses import is_dataclass
from typing import Iterable, Iterator, Union, Tuple, Sequence, Literal, Dict, Optional

from equivalib.typeform import TypeForm
from equivalib.split_type import split_type
from equivalib.super import Super
from equivalib.read_type_information import read_type_information

import equivalib.labelled_type as LT


class _AnyValue:
    """Discovery placeholder that returns True for all comparisons."""

    def __lt__(self, other: object) -> bool:
        return True

    def __le__(self, other: object) -> bool:
        return True

    def __gt__(self, other: object) -> bool:
        return True

    def __ge__(self, other: object) -> bool:
        return True

    def __eq__(self, other: object) -> bool:
        return True

    def __ne__(self, other: object) -> bool:
        return True

    def __hash__(self) -> int:
        return 0


class _DiscoverySuperInt:
    """Discovery placeholder for a Super int field that records direct integer bounds."""

    def __init__(self) -> None:
        self._lo: Optional[int] = None
        self._hi: Optional[int] = None

    def _update_lo(self, n: int) -> None:
        self._lo = n if self._lo is None else max(self._lo, n)

    def _update_hi(self, n: int) -> None:
        self._hi = n if self._hi is None else min(self._hi, n)

    def __gt__(self, other: object) -> bool:
        if isinstance(other, int) and not isinstance(other, bool):
            self._update_lo(other + 1)
        return True

    def __ge__(self, other: object) -> bool:
        if isinstance(other, int) and not isinstance(other, bool):
            self._update_lo(other)
        return True

    def __lt__(self, other: object) -> bool:
        if isinstance(other, int) and not isinstance(other, bool):
            self._update_hi(other - 1)
        return True

    def __le__(self, other: object) -> bool:
        if isinstance(other, int) and not isinstance(other, bool):
            self._update_hi(other)
        return True

    def __eq__(self, other: object) -> bool:
        if isinstance(other, int) and not isinstance(other, bool):
            self._update_lo(other)
            self._update_hi(other)
        return True

    def __ne__(self, other: object) -> bool:
        return True

    def __hash__(self) -> int:
        return id(self)

    @property
    def lo(self) -> Optional[int]:
        return self._lo

    @property
    def hi(self) -> Optional[int]:
        return self._hi


def _discover_super_int_bounds(
    dataclass_type: type,
    fields: dict[str, TypeForm],
) -> dict[str, tuple[int, int]]:
    """Run __post_init__ in discovery mode to find bounds for Super int fields."""
    super_int_fields: dict[str, _DiscoverySuperInt] = {}
    for name, ty in fields.items():
        base, _, annot = split_type(ty)
        if Super in annot and base is int:
            super_int_fields[name] = _DiscoverySuperInt()

    if not super_int_fields:
        return {}

    if not hasattr(dataclass_type, "__post_init__"):
        raise ValueError(
            f"Dataclass {dataclass_type.__name__!r} has Super int fields "
            f"({', '.join(repr(n) for n in super_int_fields)}) but no __post_init__ "
            "to derive bounds from. "
            "Add __post_init__ with explicit bound assertions, "
            "e.g. assert self.x >= 0 and assert self.x <= 9."
        )

    obj = object.__new__(dataclass_type)
    for name in fields:
        if name in super_int_fields:
            object.__setattr__(obj, name, super_int_fields[name])
        else:
            object.__setattr__(obj, name, _AnyValue())

    try:
        dataclass_type.__post_init__(obj)
    except Exception:
        pass

    bounds: dict[str, tuple[int, int]] = {}
    for name, disc in super_int_fields.items():
        lo = disc.lo
        hi = disc.hi
        if lo is None:
            raise ValueError(
                f"Could not derive lower bound for Super int field {name!r} of "
                f"{dataclass_type.__name__!r} from __post_init__. "
                f"Add an explicit assertion, e.g. 'assert self.{name} >= 0'."
            )
        if hi is None:
            raise ValueError(
                f"Could not derive upper bound for Super int field {name!r} of "
                f"{dataclass_type.__name__!r} from __post_init__. "
                f"Add an explicit assertion, e.g. 'assert self.{name} <= 9'."
            )
        bounds[name] = (lo, hi)

    return bounds


def label_bool_type() -> LT.BoolType:
    return LT.BoolType()


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

    int_bounds = _discover_super_int_bounds(base_type, free_fields)

    for name, ty in free_fields.items():
        base, _, annot = split_type(ty)
        if Super in annot and base is int:
            if name not in int_bounds:
                raise ValueError(
                    f"No bounds could be derived for Super int field {name!r} of "
                    f"{base_type.__name__!r}."
                )
            lo, hi = int_bounds[name]
            fields_dict[name] = LT.SuperType(LT.BoundedIntType(lo=lo, hi=hi))
        else:
            fields_dict[name] = label_type(ty)

    fields = tuple(fields_dict.values())

    return LT.DataclassType(constructor=base_type, fields=fields)


# pylint: disable=too-many-return-statements
def label_type(t: TypeForm) -> LT.LabelledType:
    (base_type, args, annot) = split_type(t)

    if Super in annot:
        if base_type == int:
            raise ValueError(
                "Cannot generate a standalone Super int without a containing dataclass. "
                "Wrap the field in a dataclass and provide bounds via __post_init__ assertions, "
                "e.g. assert self.x >= 0 and assert self.x <= 9."
            )
        elif base_type == bool:
            return LT.SuperType(label_bool_type())
        else:
            raise ValueError(f"Cannot generate super values of base type {repr(base_type)}.")

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
            raise ValueError(
                "Cannot generate plain int values. "
                "Use Literal[n] for a specific value, or Union[Literal[a], ..., Literal[b]] for a range."
            )
        if base_type == bool:
            return label_bool_type()
        if is_dataclass(base_type):
            return label_dataclass_type(t, base_type, args)

        raise ValueError(f"Cannot generate values of base type {repr(base_type)}.")

    raise ValueError(f"Cannot generate values of type form {repr(t)}.")


def label_type_list(types: Iterable[TypeForm]) -> Iterator[LT.LabelledType]:
    for t in types:
        yield label_type(t)
