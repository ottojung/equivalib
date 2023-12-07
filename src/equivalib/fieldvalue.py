
from dataclasses import dataclass
from typing import Union, List
from equivalib import MyType


@dataclass(frozen=True)
class Supertype:
    t: MyType


# FValueT = Union[Optional[str], str, bool, Supertype, List[object]]
FValueT = Union[object, List[object]]
