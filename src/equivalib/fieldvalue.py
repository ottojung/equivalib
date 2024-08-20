
from typing import Union
from equivalib.structure import Structure, VarName
from equivalib.supertype import Supertype


SFieldT = Union[VarName, Structure]
GFieldT = Union[Supertype, SFieldT]
