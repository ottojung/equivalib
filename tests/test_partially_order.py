
from typing import Callable, Iterable, Set, Mapping
import pytest
from equivalib import partially_order


def test_empty_list():
    assert list(partially_order([], lambda x: set())) == []


def test_singleton_list():
    assert list(partially_order([1], lambda x: set())) == [{1}]


def test_linear_order():
    elements = [1, 2, 3]
    before_relation = lambda x: set(elements[:elements.index(x)])
    assert list(partially_order(elements, before_relation)) == [{1}, {2}, {3}]


def test_partial_order():
    elements = ['a', 'b', 'c', 'd']
    before_relation = {
        'a': set(),
        'b': {'a'},
        'c': {'a'},
        'd': {'b'}
    }
    assert list(partially_order(elements, lambda x: before_relation[x])) == [{'a'}, {'b', 'c'}, {'d'}] # type: ignore


def test_incomparable_elements():
    elements = [1, 2, 3, 4]
    before_relation: Callable[[int], Iterable[int]] = lambda x: set()
    assert list(partially_order(elements, before_relation)) == [{1, 2, 3, 4}]



def test_with_a_cycle():
    elements = [1, 2, 3]
    before_relation = {1: {3}, 2: {1}, 3: {2}}
    with pytest.raises(ValueError, match='No partial order can be determined. There might be a cycle or an error in the before relation.'):
        list(partially_order(elements, lambda x: before_relation[x]))


def test_multiple_dependencies():
    elements = ['a', 'b', 'c', 'd', 'e']
    before_relation: Mapping[str, Iterable[str]] = {
        'a': set(),
        'b': {'a'},
        'c': {'b'},
        'd': {'a', 'b'},
        'e': {'c'}
    }
    assert list(partially_order(elements, before_relation)) == [{'a'}, {'b'}, {'c', 'd'}, {'e'}]


def test_complex_partial_order():
    elements = [1, 2, 3, 4, 5, 6]
    # 1 < 3, 2 < 3, 2 < 4, 5 < 6, but 1, 2, 5 are incomparable, and 3, 4, 6 are incomparable
    before_relation: Mapping[int, Set[int]] = {
        1: set(),
        2: set(),
        3: {1, 2},
        4: {2},
        5: set(),
        6: {5},
    }
    assert list(partially_order(elements, before_relation)) == [{1, 2, 5}, {3, 4, 6}]


def test_larger_set_with_duplicates():
    elements = [1, 2, 2, 3, 4, 4, 4, 5]  # Duplicates in input
    before_relation = lambda x: set(range(1, x))
    assert list(partially_order(elements, before_relation)) == [{1}, {2}, {3}, {4}, {5}]


def test_disconnected_graph():
    elements = ['a', 'b', 'c', 'd', 'e', 'f']
    before_relation: Mapping[str, Set[str]] = {
        'a': set(),
        'b': set(),
        'c': set(),
        'd': set(),
        'e': set(),
        'f': set(),
    }
    assert list(partially_order(elements, before_relation)) == [{'a', 'b', 'c', 'd', 'e', 'f'}]


def test_inverse_linear_order():
    elements = [5, 4, 3, 2, 1]
    before_relation = lambda x: set(range(1, x))
    assert list(partially_order(elements, before_relation)) == [{1}, {2}, {3}, {4}, {5}]
