
# mypy: disable-error-code="var-annotated, unused-ignore"

from typing import Callable, Iterable, Mapping
import pytest
from equivalib import partially_order, OrderedSet


def test_empty_list():
    assert list(partially_order([], lambda x: OrderedSet())) == []


def test_singleton_list():
    assert list(partially_order([1], lambda x: OrderedSet())) == [OrderedSet({1})]


def test_linear_order():
    elements = [1, 2, 3]
    before_relation = lambda x: set(elements[:elements.index(x)])
    assert list(partially_order(elements, before_relation)) == [OrderedSet({1}), OrderedSet({2}), OrderedSet({3})]


def test_partial_order():
    elements = ['a', 'b', 'c', 'd']
    before_relation = {
        'a': OrderedSet(),
        'b': OrderedSet({'a'}),
        'c': OrderedSet({'a'}),
        'd': OrderedSet({'b'}),
    }
    assert list(partially_order(elements, lambda x: before_relation[x])) == [OrderedSet({'a'}), OrderedSet({'b', 'c'}), OrderedSet({'d'})]


def test_incomparable_elements():
    elements = [1, 2, 3, 4]
    before_relation: Callable[[int], Iterable[int]] = lambda x: OrderedSet()
    assert list(partially_order(elements, before_relation)) == [OrderedSet({1, 2, 3, 4})]



def test_with_a_cycle():
    elements = [1, 2, 3]
    before_relation = {1: OrderedSet({3}), 2: OrderedSet({1}), 3: OrderedSet({2})}
    with pytest.raises(ValueError, match='No partial order can be determined. There might be a cycle or an error in the before relation.'):
        list(partially_order(elements, lambda x: before_relation[x]))


def test_multiple_dependencies():
    elements = ['a', 'b', 'c', 'd', 'e']
    before_relation: Mapping[str, Iterable[str]] = {
        'a': OrderedSet(),
        'b': OrderedSet({'a'}),
        'c': OrderedSet({'b'}),
        'd': OrderedSet({'a', 'b'}),
        'e': OrderedSet({'c'})
    }
    assert list(partially_order(elements, before_relation)) == [OrderedSet({'a'}), OrderedSet({'b'}), OrderedSet({'c', 'd'}), OrderedSet({'e'})]


def test_complex_partial_order():
    elements = [1, 2, 3, 4, 5, 6]
    # 1 < 3, 2 < 3, 2 < 4, 5 < 6, but 1, 2, 5 are incomparable, and 3, 4, 6 are incomparable
    before_relation: Mapping[int, OrderedSet[int]] = {
        1: OrderedSet(),
        2: OrderedSet(),
        3: OrderedSet({1, 2}),
        4: OrderedSet({2}),
        5: OrderedSet(),
        6: OrderedSet({5}),
    }
    assert list(partially_order(elements, before_relation)) == [OrderedSet({1, 2, 5}), OrderedSet({3, 4, 6})]


def test_larger_set_with_duplicates():
    elements = [1, 2, 2, 3, 4, 4, 4, 5]  # Duplicates in input
    before_relation = lambda x: set(range(1, x))
    assert list(partially_order(elements, before_relation)) == [OrderedSet({1}), OrderedSet({2}), OrderedSet({3}), OrderedSet({4}), OrderedSet({5})]


def test_disconnected_graph():
    elements = ['a', 'b', 'c', 'd', 'e', 'f']
    before_relation: Mapping[str, OrderedSet[str]] = {
        'a': OrderedSet(),
        'b': OrderedSet(),
        'c': OrderedSet(),
        'd': OrderedSet(),
        'e': OrderedSet(),
        'f': OrderedSet(),
    }
    assert list(partially_order(elements, before_relation)) == [OrderedSet({'a', 'b', 'c', 'd', 'e', 'f'})]


def test_inverse_linear_order():
    elements = [5, 4, 3, 2, 1]
    before_relation = lambda x: set(range(1, x))
    assert list(partially_order(elements, before_relation)) == [OrderedSet({1}), OrderedSet({2}), OrderedSet({3}), OrderedSet({4}), OrderedSet({5})]
