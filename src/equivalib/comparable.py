
from typing import Protocol


class Comparable(Protocol):
    # pylint: disable=multiple-statements
    def __gt__(self, other): pass
    def __lt__(self, other): pass
    def __ge__(self, other): pass
    def __le__(self, other): pass
