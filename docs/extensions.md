# `Extension`-subclass based custom leaves for `equivalib.core.generate`

This document defines the extension design for custom class leaves in `equivalib.core.generate`.

## Scope

Custom leaves are discovered from the class itself. A custom class leaf participates only when it is a subtype of `Extension`.

Core leaf language remains built-in and unchanged for:

- `bool`
- `int` (named/bounded as defined in the core spec)
- `tuple[...]`
- `union` (`typing.Union[...]` / `|`)
- supported `Literal[...]` forms

For any class leaf outside that base language, generation checks whether that class is a subtype of `Extension` and provides the required methods below.

---

## Public API

`generate` has this signature:

```python
def generate(
    tree: Type[GenerateT],
    constraint: Expression = _DEFAULT_CONSTRAINT,
    methods: Optional[Mapping[Label, Method]] = None,
) -> set[GenerateT]:
    ...
```


---

## Required `Extension` Base Class

The contract is defined by an abstract base class:

```python
from abc import ABC, abstractmethod


class Extension(ABC):
    @staticmethod
    @abstractmethod
    def initialize(tree: Type[T], constraint: Expression) -> Optional[Expression]:
        ...

    @staticmethod
    @abstractmethod
    def enumerate_all(tree: Type[T], constraint: Expression, address: Optional[str]) -> Iterator[A]:
        ...

    @staticmethod
    @abstractmethod
    def arbitrary(tree: Type[T], constraint: Expression, address: Optional[str]) -> Optional[A]:
        ...

    @staticmethod
    @abstractmethod
    def uniform_random(tree: Type[T], constraint: Expression, address: Optional[str]) -> Optional[A]:
        ...
```

A non-base class leaf must be a subtype of `Extension`.

Semantics:

- `initialize` returns additional boolean constraints (or `None`).
- `enumerate_all` provides exhaustive admissible values for the occurrence.
- `arbitrary` provides one admissible witness value (or `None` if none exists).
- `uniform_random` provides one admissible witness value with core uniform-random semantics (or `None` if none exists).

`initialize` is called once per participating extension class per `generate(...)` call.

---

## Discovery and Ownership Rules

Given a leaf syntax `L`:

1. If `L` is a core base leaf (`bool`, `int`, tuple, union, supported literals), core behavior applies.
2. Otherwise if `L` is a class and `issubclass(L, Extension)` is true, that class owns the leaf.
3. Otherwise generation fails (unsupported leaf / class is not an `Extension` subtype).


---

## Effective Constraint

For each participating extension class `C`:

```python
extra_C = C.initialize(tree, constraint)
```

The effective constraint is:

```text
constraint_eff = And(constraint, extra_C1, extra_C2, ...)
```

with `None` entries omitted.

All later validation/search/method dispatch and extension hook calls use `constraint_eff`.

---

## Address Semantics

`address` identifies the owned occurrence:

- Named occurrence `Annotated[..., Name("X")]` → `"X"`
- Reachable tuple child from addressable parent → bracket path (e.g. `"X[0]"`, `"X[1][2]"`, `"[0][1]"`)
- Otherwise `None`

Repeated identical labels denote the same logical variable.

---

## Method Dispatch

Per-label method selection remains core behavior:

- default method: `"all"`
- explicit methods: `"all"`, `"arbitrary"`, `"uniform_random"`

For extension-owned occurrences:

- `"all"` → `enumerate_all(...)`
- `"arbitrary"` → `arbitrary(...)`
- `"uniform_random"` → `uniform_random(...)`

---

## Typing/Expression Semantics

Extension-owned leaves are atomic unless explicitly specified otherwise by future revisions.

Therefore by default:

- equality / inequality on whole value are valid,
- non-empty sub-addressing into the leaf is invalid,
- arithmetic and ordering on the leaf are invalid,
- boolean connectives using the leaf as a boolean term are invalid.

Built-in types keep built-in expression typing.

---

## Finite vs Infinite Domains

- `enumerate_all` must only be used when exhaustive support is finite.
- Exhaustive generation over infinite support must raise.
- `uniform_random` requires finite, sampleable support with defined weighting.
- `arbitrary` may return a witness on infinite support.

---

## Error Conditions

Generation must fail when:

- a non-base class leaf is not a subtype of `Extension`,
- required `Extension` methods are missing or non-callable,
- `initialize` returns a non-expression or non-boolean expression,
- hook outputs are inadmissible for the addressed occurrence,
- invalid expression operations are applied to atomic extension-owned leaves,
- exhaustive or uniform-random generation is requested for unsupported infinite domains.

---

## Examples

### Class-owned custom leaves (`Extension` subtypes)

```python
from dataclasses import dataclass
from typing import Annotated, Iterator

from equivalib.core import (
    BooleanExpression,
    Extension,
    Name,
    generate,
)


@dataclass(frozen=True)
class Greeting(Extension):
    text: str

    @staticmethod
    def initialize(tree: object, constraint: object) -> object:
        del tree, constraint
        return None

    @staticmethod
    def enumerate_all(tree: object, constraint: object, address: str | None) -> Iterator["Greeting"]:
        del tree, constraint, address
        return iter((Greeting("hello"), Greeting("hi")))

    @staticmethod
    def arbitrary(tree: object, constraint: object, address: str | None) -> "Greeting" | None:
        del tree, constraint, address
        return Greeting("hello")

    @staticmethod
    def uniform_random(tree: object, constraint: object, address: str | None) -> "Greeting" | None:
        del tree, constraint, address
        return Greeting("hi")


assert generate(Greeting, BooleanExpression(True), {}) == {Greeting("hello"), Greeting("hi")}
assert generate(
    Annotated[Greeting, Name("G")],
    BooleanExpression(True),
    {"G": "arbitrary"},
) == {Greeting("hello")}
```

For regex families, `Regex` is the abstract helper base that owns mechanics (`initialize`, `enumerate_all`, `arbitrary`, `uniform_random`). The `regex` factory is the recommended way to create a concrete regex type from a pattern string:

```python
from typing import Annotated

from equivalib.core import Name, generate, regex


RegexABorCD = regex("(ab|cd)")

generate(RegexABorCD)
generate(Annotated[RegexABorCD, Name("R")], methods={"R": "arbitrary"})
```

You can also define a concrete subclass manually when you need a named type:

```python
from typing import Annotated

from equivalib.core import Name, Regex, generate


class RegexABorCD(Regex):
    @staticmethod
    def expression() -> str:
        return "(ab|cd)"


generate(RegexABorCD)
generate(Annotated[RegexABorCD, Name("R")], methods={"R": "arbitrary"})
```

For integer interval families, `LineIntervalsSet` is the abstract helper base. The `intervals` factory is the recommended way to create a concrete subclass from a range and count:

```python
from typing import Annotated

from equivalib.core import Name, generate, intervals


PairsUpTo5 = intervals(on=(0, 5), n=2)

generate(PairsUpTo5)
generate(Annotated[PairsUpTo5, Name("I")], methods={"I": "arbitrary"})
```

You can also define a concrete subclass manually when you need a named type:

```python
from typing import Annotated

from equivalib.core import LineIntervalsSet, Name, generate


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


generate(PairsUpTo5)
generate(Annotated[PairsUpTo5, Name("I")], methods={"I": "arbitrary"})
```
