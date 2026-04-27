# Equivalib: Constraint-Driven Test Case Generation

## Slide 1 — Why this library exists

- Most bugs live in **combinations**, not isolated values.
- Hand-picking examples misses edge interactions.
- `equivalib` lets us describe a value space and generate concrete cases systematically.

---

## Slide 2 — Smallest possible example (one boolean)

```python
from equivalib.core import generate

values = generate(bool)
# => {False, True}
```

This is the base mental model: describe a type, get the concrete values.

---

## Slide 3 — Next step (tuple of booleans)

```python
from typing import Tuple
from equivalib.core import generate

values = generate(Tuple[bool, bool])
# => {
#      (False, False),
#      (False, True),
#      (True, False),
#      (True, True),
#    }
```

Now we already see interaction coverage (all pairwise boolean combinations).

---

## Slide 4 — Direct indexing on generated structures

```python
from typing import Tuple
from equivalib.core import generate

values = generate(Tuple[bool, bool])
only_true_first = {item for item in values if item[0] is True}
# => {(True, False), (True, True)}
```

Use direct indexing (`item[0]`, `item[1]`) when discussing tuple positions.

---

## Slide 5 — Core extension example: finite regex language

```python
from equivalib.core import Regex, generate

class TicketCode(Regex):
    @staticmethod
    def expression() -> str:
        return r"(AB|CD)\d{2}"

codes = generate(TicketCode)
# 200 total values: AB00..AB99 and CD00..CD99
```

This is great for IDs/tokens without hardcoding large fixture lists.

---

## Slide 6 — Harder extension: Pythagorean triples

```python
from typing import Iterator
from equivalib.core import Extension, BooleanExpression, generate
from equivalib.core.expression import Expression

class PythagoreanTriple(Extension):
    def __init__(self, value: tuple[int, int, int]):
        self.value = value

    def __hash__(self) -> int:
        return hash(self.value)

    def __eq__(self, other: object) -> bool:
        return isinstance(other, PythagoreanTriple) and self.value == other.value

    @staticmethod
    def initialize(tree: object, constraint: Expression) -> None:
        del tree, constraint

    @staticmethod
    def enumerate_all(tree: object, constraint: Expression, address: str | None) -> Iterator["PythagoreanTriple"]:
        del tree, constraint, address
        for a in range(1, 31):
            for b in range(a, 31):
                for c in range(b, 31):
                    if (a * a) + (b * b) == (c * c):
                        yield PythagoreanTriple((a, b, c))

    @staticmethod
    def arbitrary(tree: object, constraint: Expression, address: str | None) -> "PythagoreanTriple" | None:
        del tree, constraint, address
        return PythagoreanTriple((3, 4, 5))

    @staticmethod
    def uniform_random(tree: object, constraint: Expression, address: str | None) -> "PythagoreanTriple" | None:
        del tree, constraint, address
        return PythagoreanTriple((8, 15, 17))

triples = generate(PythagoreanTriple, BooleanExpression(True))
# includes (3, 4, 5), (5, 12, 13), (20, 21, 29), ...
```

This shows how to encode mathematical domains as reusable generators.

---

## Slide 7 — Why this is practical for testing

- Start tiny (`bool`, then tuples).
- Scale to realistic domains (regexes, math structures).
- Keep examples executable as tests.

---

## Slide 8 — Takeaway

**equivalib helps teams move from ad-hoc examples to structured, reproducible value generation.**

The examples above are intentionally ordered from easy to harder, and each one is mirrored in `tests/test_interesting.py`.
