
from dataclasses import dataclass
from typing import Any

@dataclass(frozen=True)
class Constant:
    value: Any

    def __str__(self) -> str:
        return repr(self.value)
