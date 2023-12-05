
from dataclasses import dataclass

@dataclass(frozen=True)
class Constant:
    value: object

    def __str__(self) -> str:
        return repr(self.value)
