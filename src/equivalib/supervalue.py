
from dataclasses import field
from typing import TypeVar

FieldT = TypeVar('FieldT')

def supervalue(**kwargs: FieldT) -> FieldT:
    # pylint: disable=invalid-field-call
    return field(**kwargs, metadata={'super': True}) # type: ignore
