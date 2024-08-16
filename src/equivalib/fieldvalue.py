
from dataclasses import dataclass
from typing import Union
from equivalib.mytype import MyGenType
from equivalib.structure import Structure, VarName


@dataclass(frozen=True)
class Supertype:
    t: MyGenType


SFieldT = Union[VarName, Structure]
GFieldT = Union[Supertype, SFieldT]
