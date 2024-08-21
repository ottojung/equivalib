
from dataclasses import dataclass
from equivalib.typeform import TypeForm


@dataclass(frozen=True)
class Supertype:
    t: TypeForm
