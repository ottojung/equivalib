from __future__ import annotations

import random
import re
import sre_parse
from abc import ABC, abstractmethod
from dataclasses import dataclass
from functools import lru_cache
from itertools import product
from typing import Any, Iterator, Type, cast

from equivalib.core.extension import Extension
from equivalib.core.expression import ParsedExpression

_DEFAULT_INFINITE_REPEAT_BOUND = 8


@dataclass(frozen=True)
class Regex(Extension, ABC):
    value: str

    @staticmethod
    @abstractmethod
    def expression() -> str:
        raise NotImplementedError

    @classmethod
    def _compiled(cls) -> re.Pattern[str]:
        return re.compile(cls.expression())

    @classmethod
    def _parsed(cls) -> sre_parse.SubPattern:
        return sre_parse.parse(cls.expression())

    @classmethod
    def _materialize(cls, text: str) -> "Regex":
        return cls(text)

    @staticmethod
    def initialize(tree: object, constraint: ParsedExpression) -> None:
        del tree, constraint

    @classmethod
    def enumerate_all(cls, tree: object, constraint: ParsedExpression, address: str | None) -> Iterator["Regex"]:
        del tree, constraint, address
        for text in _enumerate_subpattern(cls._parsed()):
            if cls._compiled().fullmatch(text):
                yield cls._materialize(text)

    @classmethod
    def arbitrary(cls, tree: object, constraint: ParsedExpression, address: str | None) -> "Regex" | None:
        del tree, constraint, address
        for text in _enumerate_subpattern(cls._parsed(), infinite_bound=_DEFAULT_INFINITE_REPEAT_BOUND):
            if cls._compiled().fullmatch(text):
                return cls._materialize(text)
        return None

    @classmethod
    def uniform_random(cls, tree: object, constraint: ParsedExpression, address: str | None) -> "Regex" | None:
        del tree, constraint, address
        pool = tuple(_enumerate_subpattern(cls._parsed(), infinite_bound=_DEFAULT_INFINITE_REPEAT_BOUND))
        if not pool:
            return None
        return cls._materialize(random.choice(pool))


@lru_cache(maxsize=None)
def regex(expression: str) -> Type[Regex]:
    class CustomRegex(Regex):
        @staticmethod
        def expression() -> str:
            return expression

    CustomRegex.__name__ = f"Regex({expression!r})"
    CustomRegex.__qualname__ = f"Regex({expression!r})"
    return CustomRegex


def _enumerate_subpattern(
    pattern: sre_parse.SubPattern,
    infinite_bound: int | None = None,
) -> Iterator[str]:
    current = [""]
    for op, arg in pattern.data:
        pieces = list(_enumerate_token(op, arg, infinite_bound))
        if not pieces:
            return
        current = [prefix + suffix for prefix, suffix in product(current, pieces)]
    yield from current


def _enumerate_token(
    op: object,
    arg: object,
    infinite_bound: int | None,
) -> Iterator[str]:
    if op is sre_parse.LITERAL:
        yield chr(cast(int, arg))
        return

    if op is sre_parse.ANY:
        for c in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_":
            yield c
        return

    if op is sre_parse.IN:
        for c in _enumerate_in(cast(list[tuple[object, object]], arg)):
            yield c
        return

    if op is sre_parse.BRANCH:
        _, branches = cast(tuple[Any, list[sre_parse.SubPattern]], arg)
        for branch in branches:
            yield from _enumerate_subpattern(branch, infinite_bound)
        return

    if op is sre_parse.SUBPATTERN:
        _gid, _add_flags, _del_flags, nested = cast(tuple[Any, Any, Any, sre_parse.SubPattern], arg)
        yield from _enumerate_subpattern(nested, infinite_bound)
        return

    if op in (sre_parse.MAX_REPEAT, sre_parse.MIN_REPEAT):
        lo, hi, nested = cast(tuple[int, int, sre_parse.SubPattern], arg)
        if hi == sre_parse.MAXREPEAT:
            if infinite_bound is None:
                raise ValueError("Regex enumerate_all does not support unbounded repeats.")
            hi = max(lo, infinite_bound)
        base = tuple(_enumerate_subpattern(nested, infinite_bound))
        for count in range(lo, hi + 1):
            if count == 0:
                yield ""
                continue
            for chunk in product(base, repeat=count):
                yield "".join(chunk)
        return

    if op is sre_parse.CATEGORY:
        cat = arg
        if cat == sre_parse.CATEGORY_DIGIT:
            yield from "0123456789"
            return
        if cat == sre_parse.CATEGORY_SPACE:
            yield from (" ", "\t")
            return
        if cat == sre_parse.CATEGORY_WORD:
            yield from "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_"
            return
        raise ValueError(f"Unsupported regex category: {cat!r}")

    if op is sre_parse.AT:
        yield ""
        return

    raise ValueError(f"Unsupported regex op: {op!r}")


def _enumerate_in(arg: list[tuple[object, object]]) -> Iterator[str]:
    negate = False
    pieces: list[str] = []
    for in_op, in_arg in arg:
        if in_op is sre_parse.NEGATE:
            negate = True
            continue
        if in_op is sre_parse.LITERAL:
            pieces.append(chr(cast(int, in_arg)))
            continue
        if in_op is sre_parse.RANGE:
            lo, hi = cast(tuple[int, int], in_arg)
            for code in range(lo, hi + 1):
                pieces.append(chr(code))
            continue
        if in_op is sre_parse.CATEGORY:
            if in_arg == sre_parse.CATEGORY_DIGIT:
                pieces.extend("0123456789")
                continue
            if in_arg == sre_parse.CATEGORY_WORD:
                pieces.extend("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_")
                continue
            raise ValueError(f"Unsupported regex IN category: {in_arg!r}")
        raise ValueError(f"Unsupported regex IN op: {in_op!r}")

    if not negate:
        yield from dict.fromkeys(pieces)
        return

    universe = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_"
    excluded = set(pieces)
    for c in universe:
        if c not in excluded:
            yield c
