
from typing import Tuple, Union, NewType
from dataclasses import dataclass

from equivalib.labelled_type import LabelledType
from equivalib.mytype import MyType
from equivalib.constant import Constant


VarName = NewType('VarName', str)
StructureArgument = Union[VarName, Constant]


@dataclass(frozen=True)
class Structure:
    constructor: MyType
    signature: LabelledType
    arguments: Tuple[StructureArgument, ...]
