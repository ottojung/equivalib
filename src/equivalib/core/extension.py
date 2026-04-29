from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Iterator, Optional

from equivalib.core.expression import ParsedExpression

class Extension(ABC):
    @staticmethod
    @abstractmethod
    def initialize(tree: object, constraint: ParsedExpression) -> Optional[ParsedExpression]:
        raise NotImplementedError

    @staticmethod
    @abstractmethod
    def enumerate_all(
        tree: object,
        constraint: ParsedExpression,
        address: str | None,
    ) -> Iterator["Extension"]:
        raise NotImplementedError

    @staticmethod
    @abstractmethod
    def arbitrary(
        tree: object,
        constraint: ParsedExpression,
        address: str | None,
    ) -> "Extension" | None:
        raise NotImplementedError

    @staticmethod
    @abstractmethod
    def uniform_random(
        tree: object,
        constraint: ParsedExpression,
        address: str | None,
    ) -> "Extension" | None:
        raise NotImplementedError
