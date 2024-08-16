
from typing import Tuple, Union, NewType
from dataclasses import dataclass

from equivalib.mytype import MyGenType, MyType
from equivalib.constant import Constant


VarName = NewType('VarName', str)
StructureArgument = Union[VarName, Constant]


@dataclass(frozen=True)
class Structure:
    constructor: MyType
    signature: MyGenType
    arguments: Tuple[StructureArgument, ...]
