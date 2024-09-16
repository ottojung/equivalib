## Copyright (C) 2023  Otto Jung
## This program is free software: you can redistribute it and/or modify it under the terms of the GNU General Public License as published by the Free Software Foundation; version 3 of the License. This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more details. You should have received a copy of the GNU General Public License along with this program.  If not, see <http://www.gnu.org/licenses/>.

from typing import Callable, TypeVar, Iterable, Union, Mapping, Iterator, Sequence, List, Set

T = TypeVar('T')
BeforeType = Union[Callable[[T], Iterable[T]], Mapping[T, Iterable[T]]]

def partially_order(elements: Iterable[T], before: BeforeType[T]) -> Iterator[Sequence[T]]:
    """
    Turns `elements` into "levels" of partially ordered elements.
    Elements that are incomparable are on the same "level" in the resulting list.
    """

    if callable(before):
        get_before = before
    else:
        get_before = lambda x: before.get(x, [])

    # A dictionary to keep track of elements that have not been placed into a level yet.
    remaining_list: List[T] = list(elements)
    remaining_set: Set[T] = set(remaining_list)

    while remaining_list:
        # The new level will contain elements such that there are
        # no other elements that should come before them
        # based on the remaining elements.
        new_level: List[T] = []

        for elem in remaining_list:
            # Get the set of elements that should come before the current element.
            smaller_elements = set(get_before(elem))
            if smaller_elements.isdisjoint(remaining_set):
                # If none of the 'smaller' elements are in the remaining set,
                # it means this element is not preceded by any other remaining
                # elements and can be part of the new level.
                new_level.append(elem)

        if not new_level:
            raise ValueError('No partial order can be determined. '
                             'There might be a cycle or an error in the before relation.')

        # Add the new level to the list of levels.
        yield new_level

        # Remove the new level from the set of remaining elements.
        for elem in new_level:
            if elem in remaining_set:
                remaining_set.remove(elem)
                while elem in remaining_list:
                    remaining_list.remove(elem)
