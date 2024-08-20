
from typing import Type, TypeAlias, Union

MyType: TypeAlias = Type[object]
MyGenType: TypeAlias = Union[MyType, object]
