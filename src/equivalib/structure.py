
from typing import Tuple, Union, NewType
from dataclasses import dataclass

from equivalib.typeform import TypeForm
from equivalib.mytype import MyType
from equivalib.constant import Constant


VarName = NewType('VarName', str)
StructureArgument = Union[VarName, Constant]


@dataclass(frozen=True)
class Structure:
    constructor: MyType
    signature: TypeForm
    arguments: Tuple[StructureArgument, ...]
