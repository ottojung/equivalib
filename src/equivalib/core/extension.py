from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Iterator, Optional, TypeVar

from equivalib.core.expression import Expression

ExtensionT = TypeVar("ExtensionT", bound="Extension")


class Extension(ABC):
    @staticmethod
    @abstractmethod
    def initialize(tree: object, constraint: Expression) -> Optional[Expression]:
        raise NotImplementedError

    @staticmethod
    @abstractmethod
    def enumerate_all(
        tree: object,
        constraint: Expression,
        address: str | None,
    ) -> Iterator[ExtensionT]:
        raise NotImplementedError

    @staticmethod
    @abstractmethod
    def arbitrary(
        tree: object,
        constraint: Expression,
        address: str | None,
    ) -> ExtensionT | None:
        raise NotImplementedError

    @staticmethod
    @abstractmethod
    def uniform_random(
        tree: object,
        constraint: Expression,
        address: str | None,
    ) -> ExtensionT | None:
        raise NotImplementedError
