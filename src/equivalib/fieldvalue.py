
from typing import Union
from equivalib.structure import Structure, VarName

import equivalib.labelled_type as LT


SFieldT = Union[VarName, Structure]
GFieldT = Union[LT.SuperType, SFieldT]
