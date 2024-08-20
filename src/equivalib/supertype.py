
from dataclasses import dataclass
from equivalib.mytype import MyGenType


@dataclass(frozen=True)
class Supertype:
    t: MyGenType
