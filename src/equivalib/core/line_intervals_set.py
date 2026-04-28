from __future__ import annotations

import random
from abc import ABC, abstractmethod
from dataclasses import dataclass
from itertools import combinations_with_replacement, permutations
from typing import Iterator

from equivalib.core.extension import Extension
from equivalib.core.expression import Expression

# Relation codes used to classify how two integer intervals relate to each other.
_RELATION_TOUCH = 0
_RELATION_KISS = 1
_RELATION_OVERLAP = 2
_RELATION_DISJOINT = 3


def _relation_code(left: tuple[int, int], right: tuple[int, int]) -> int:
    left_start, left_end = left
    right_start, right_end = right

    if left_end + 1 < right_start or right_end + 1 < left_start:
        return _RELATION_DISJOINT
    if left_end + 1 == right_start or right_end + 1 == left_start:
        return _RELATION_KISS
    if left_end == right_start or right_end == left_start:
        return _RELATION_TOUCH
    if left_start < right_end and right_start < left_end:
        return _RELATION_OVERLAP
    raise AssertionError(f"Unclassifiable interval pair: {left!r}, {right!r}")


def _canonical_signature(intervals: tuple[tuple[int, int], ...]) -> tuple[int, ...]:
    """Return the lexicographically smallest pairwise-relation tuple over all permutations."""
    count = len(intervals)
    if count == 0:
        return ()
    best: tuple[int, ...] | None = None
    for order in permutations(range(count)):
        candidate = tuple(
            _relation_code(intervals[order[i]], intervals[order[j]])
            for i in range(count)
            for j in range(i + 1, count)
        )
        if best is None or candidate < best:
            best = candidate
    return best or ()


@dataclass(frozen=True)
class LineIntervalsSet(Extension, ABC):
    """Abstract base class for generating non-equivalent sets of integer line intervals.

    Concrete subclasses must declare:
      - ``number_of_intervals()`` – how many intervals each representative contains.
      - ``range_minimum()`` – the inclusive lower bound for interval endpoints.
      - ``range_maximum()`` – the inclusive upper bound for interval endpoints.

    ``generate(MyLineIntervalsSet)`` then returns exactly one representative from
    every equivalence class of *n*-tuples of valid intervals drawn from
    ``[range_minimum(), range_maximum()]``, where two tuples are equivalent when
    one can be obtained from the other by reordering.  The equivalence is defined
    by the canonical pairwise relation signature (touch / kiss / overlap / disjoint).

    Example::

        class PairsUpTo5(LineIntervalsSet):
            @classmethod
            def number_of_intervals(cls) -> int:
                return 2

            @classmethod
            def range_minimum(cls) -> int:
                return 0

            @classmethod
            def range_maximum(cls) -> int:
                return 5

        # Produces one set per equivalence class:
        # touch, kiss, overlap, disjoint → 4 representatives
        representatives = generate(PairsUpTo5)
    """

    intervals: tuple[tuple[int, int], ...]

    @classmethod
    @abstractmethod
    def number_of_intervals(cls) -> int:
        raise NotImplementedError

    @classmethod
    @abstractmethod
    def range_minimum(cls) -> int:
        raise NotImplementedError

    @classmethod
    @abstractmethod
    def range_maximum(cls) -> int:
        raise NotImplementedError

    @classmethod
    def _all_intervals(cls) -> list[tuple[int, int]]:
        lo = cls.range_minimum()
        hi = cls.range_maximum()
        return [(s, e) for s in range(lo, hi + 1) for e in range(s, hi + 1)]

    @classmethod
    def _enumerate_representatives(cls) -> Iterator[tuple[tuple[int, int], ...]]:
        seen: set[tuple[int, ...]] = set()
        for combo in combinations_with_replacement(cls._all_intervals(), cls.number_of_intervals()):
            sig = _canonical_signature(combo)
            if sig not in seen:
                seen.add(sig)
                yield combo

    @classmethod
    def _materialize(cls, intervals: tuple[tuple[int, int], ...]) -> "LineIntervalsSet":
        return cls(intervals)

    @staticmethod
    def initialize(tree: object, constraint: Expression) -> None:
        del tree, constraint

    @classmethod
    def enumerate_all(cls, tree: object, constraint: Expression, address: str | None) -> Iterator["LineIntervalsSet"]:
        del tree, constraint, address
        for intervals in cls._enumerate_representatives():
            yield cls._materialize(intervals)

    @classmethod
    def arbitrary(cls, tree: object, constraint: Expression, address: str | None) -> "LineIntervalsSet | None":
        del tree, constraint, address
        for intervals in cls._enumerate_representatives():
            return cls._materialize(intervals)
        return None

    @classmethod
    def uniform_random(cls, tree: object, constraint: Expression, address: str | None) -> "LineIntervalsSet | None":
        del tree, constraint, address
        pool = list(cls._enumerate_representatives())
        if not pool:
            return None
        return cls._materialize(random.choice(pool))
