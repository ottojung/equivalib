
from typing import TypeVar

OSKey = TypeVar('OSKey')

class OrderedSet(dict[OSKey, None]):
    def __init__(self, iterable=None):
        if iterable is not None:
            for item in iterable:
                self[item] = None

    def add(self, item):
        self[item] = None

    def discard(self, item):
        self.pop(item, None)

    def isdisjoint(self, other):
        return not any(item in self for item in other)

    def difference_update(self, other):
        for item in other:
            self.discard(item)

    def __iter__(self):
        return iter(self.keys())

    def __contains__(self, key):
        return key in self.keys()

    def __len__(self):
        return len(self.keys())
