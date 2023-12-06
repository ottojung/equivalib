## Copyright (C) 2023  Otto Jung
## This program is free software: you can redistribute it and/or modify it under the terms of the GNU General Public License as published by the Free Software Foundation; version 3 of the License. This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more details. You should have received a copy of the GNU General Public License along with this program.  If not, see <http://www.gnu.org/licenses/>.

from typing import Callable, TypeVar, Set, Generator, Iterable, Union, Mapping

T = TypeVar('T')
BeforeType = Union[Callable[[T], Iterable[T]], Mapping[T, Iterable[T]]]

def partially_order(elements: Iterable[T], before: BeforeType[T]) -> Generator[Set[T], None, None]:
    """
    Turns `elements` into "levels" of partially ordered elements.
    Elements that are incomparable are on the same "level" in the resulting list.
    """

    if isinstance(before, dict):
        get_before: Callable[[T], Iterable[T]] = lambda x: before[x]
    elif callable(before):
        get_before = before
    else:
        raise TypeError(f"Expected either a dict or callable, got {before!r}")

    # A dictionary to keep track of elements that have not been placed into a level yet.
    remaining = set(elements)

    while remaining:
        # The new level will contain elements such that there are
        # no other elements that should come before them
        # based on the remaining elements.
        new_level: Set[T] = set()

        for elem in remaining:
            # Get the set of elements that should come before the current element.
            smaller_elements = set(get_before(elem))
            if smaller_elements.isdisjoint(remaining):
                # If none of the 'smaller' elements are in the remaining set,
                # it means this element is not preceded by any other remaining
                # elements and can be part of the new level.
                new_level.add(elem)

        if not new_level:
            raise ValueError('No partial order can be determined. '
                             'There might be a cycle or an error in the before relation.')

        # Add the new level to the list of levels.
        yield new_level

        # Remove the new level from the set of remaining elements.
        remaining.difference_update(new_level)
