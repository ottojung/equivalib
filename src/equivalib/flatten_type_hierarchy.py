
from typing import Iterable, Iterator

from equivalib.typeform import TypeForm


def flatten_type_hierarchy(types: Iterable[Iterable[TypeForm]]) -> Iterator[TypeForm]:
    # TODO: sort such that Super types are generated later. This is an optimization.

    for group in types:
        yield from group
