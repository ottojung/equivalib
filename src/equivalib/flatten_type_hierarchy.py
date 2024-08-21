
from typing import Iterable, Iterator

from equivalib.typeform import TypeForm


def flatten_type_hierarchy(types: Iterable[Iterable[TypeForm]]) -> Iterator[TypeForm]:
    for group in types:
        yield from group
