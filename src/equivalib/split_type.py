
import typing
from typing import Tuple, List


def split_type(t: object) -> Tuple[object, List[object], List[object]]:
    base0 = typing.get_origin(t) or t
    args0 = list(typing.get_args(t))

    if args0 is None:
        args0 = []

    if base0 == typing.Annotated:
        c_annotations = args0[1:]
        (base, args, r_annot) = split_type(args0[0])
        annotations = list(c_annotations) + list(r_annot)
    else:
        base = base0
        args = args0
        annotations = []

    return (base, args, annotations)
