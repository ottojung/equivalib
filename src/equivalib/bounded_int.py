
from typing import Tuple

from equivalib.value_range import ValueRange
from equivalib.split_type import split_type


def unpack_bounded_int(t: object) -> Tuple[int, int]:
    (_base, _args, annot) = split_type(t)

    if not annot:
        raise ValueError("Can only generate annotated integers like `Annotated[int, ValueRange(3, 9)]`.")

    value_range_list = [x for x in annot if isinstance(x, ValueRange)]
    if not value_range_list:
        raise ValueError("Can only generate integers annotated with ValueRange, like `Annotated[int, ValueRange(3, 9)]`.")
    if len(value_range_list) > 1:
        raise ValueError("Multiple ValueRange annotations for int is not allowed..")

    value_range = value_range_list[0]
    low, high = (value_range.min, value_range.max)

    return low, high
