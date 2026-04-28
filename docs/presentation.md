# Equivalib: Constraint-Driven Test Case Generation

## Slide 1 — Why this library exists

- Most test failures come from **interactions**, not isolated values.
- Handwritten fixtures usually under-sample the real state space.
- `equivalib` lets you describe **what must hold**, then generates values that satisfy it.
- One line can produce exhaustive coverage; one flag switches to a single canonical witness.

---

## Slide 2 — One-line start: finite booleans

```python
from equivalib.core import generate

values = generate(bool)
# => {False, True}
```

The simplest case is still useful: this is full exhaustive generation for `bool`.

---

## Slide 3 — Product types: tuple domains

```python
from equivalib.core import generate

values = generate(tuple[bool, bool])
# => {
#      (False, False),
#      (False, True),
#      (True, False),
#      (True, True),
#    }
```

Cartesian products are generated automatically for unnamed tuple trees.

---

## Slide 4 — Post-filtering as a quick triage pattern

```python
from equivalib.core import generate

values = generate(tuple[bool, bool])
only_true_first = {item for item in values if item[0]}
# => {(True, False), (True, True)}
```

Great for demos, quick checks, and building intuition.

---

## Slide 5 — In-model constraints via named trees + `reference`

```python
from typing import Annotated, cast
from equivalib.core import Eq, Name, generate
from equivalib.core.expression import reference

tree = cast(type[tuple[bool, bool]], Annotated[tuple[bool, bool], Name("B")])
constraint = Eq(reference("B", 0), reference("B", 1))

values = generate(tree, constraint, {"B": "all"})
# => {(False, False), (True, True)}
```

Instead of filtering after generation, we encode relationships directly into the solver input.

---

## Slide 6 — Literal union types

```python
from typing import Literal
from equivalib.core import generate

values = generate(Literal["red", "green", "blue"])
# => {"red", "green", "blue"}
```

`Literal` types are fully supported as finite leaf domains — no extension needed.

---

## Slide 7 — Union of literal types for richer domains

```python
from typing import Literal, Union
from equivalib.core import generate

values = generate(Union[Literal[1, 2, 3], bool])
# => {False, True, 1, 2, 3}
```

Union deduplicates across branches using Python's standard identity rules.

---

## Slide 8 — Extension example: finite regex language

```python
from equivalib.core import Regex, generate

class TicketCode(Regex):
    @staticmethod
    def expression() -> str:
        return r"(AB|CD)\d{2}"

codes = generate(TicketCode)
# => 200 values: AB00..AB99 and CD00..CD99
```

Extensions let domain-specific classes plug into the same generation flow.

---

## Slide 9 — Realistic data slicing on generated extensions

```python
codes = generate(TicketCode)
ab_prefixed = {code for code in codes if str(code.value).startswith("AB")}

# len(ab_prefixed) == 100
# TicketCode("AB42") in ab_prefixed
# TicketCode("CD42") not in ab_prefixed
```

This pattern keeps generation declarative while still allowing business-level subsets.

---

## Slide 10 — SAT-backed integer relations: Pythagorean triples

```python
from equivalib.core import generate, And, Ge, Le, Eq, Add, Mul, IntegerConstant
from equivalib.core.expression import reference

def generate_pythagorean_triples(limit: int):
    tree = tuple[int, int, int]
    a, b, c = reference(0), reference(1), reference(2)
    bounds = And(
        And(Ge(a, IntegerConstant(1)), Le(a, IntegerConstant(limit))),
        And(Ge(b, IntegerConstant(1)), Le(b, IntegerConstant(limit))),
        And(Ge(c, IntegerConstant(1)), Le(c, IntegerConstant(limit))),
    )
    ordered    = And(Le(a, b), Le(b, c))
    pythagorean = Eq(Add(Mul(a, a), Mul(b, b)), Mul(c, c))
    return generate(tree, And(bounds, And(ordered, pythagorean)))

triples = generate_pythagorean_triples(limit=30)
# includes (3, 4, 5), (5, 12, 13), (20, 21, 29), ...
```

SAT-backed integer constraints scale to large search spaces with precise semantics.

---

## Slide 11 — Canonical witness on huge spaces

```python
values = generate_sum_to_hundred_witness()
# => exactly one tuple witness (10 binary values summing to 5)
```

Using `{"X": "arbitrary"}` asks for one deterministic witness instead of exhaustive enumeration.

---

## Slide 12 — Mixing generation modes per label

```python
from typing import Annotated
from equivalib.core import generate, And, Gt, Name
from equivalib.core.expression import reference

tree = tuple[Annotated[int, Name("X")], Annotated[int, Name("Y")]]
constraint = And(
    And(Ge(reference("X"), IntegerConstant(0)), Le(reference("X"), IntegerConstant(9))),
    And(Ge(reference("Y"), IntegerConstant(0)), Le(reference("Y"), IntegerConstant(9))),
    Gt(reference("X"), reference("Y")),
)

result = generate(tree, constraint, {"X": "all", "Y": "arbitrary"})
# => {(1,0), (2,0), (3,0), (4,0), (5,0), (6,0), (7,0), (8,0), (9,0)}
```

`"all"` on `X` exhausts every valid value; `"arbitrary"` on `Y` pins to one canonical choice.

---

## Slide 13 — Practical generation modes

- `"all"`: exhaustive values (small/finite spaces).
- `"arbitrary"`: one canonical satisfying witness.
- `"uniform_random"`: one random satisfying witness.

Use per-label methods to mix exhaustive and witness-oriented generation.

---

## Slide 14 — Custom Extension: non-regex leaf types

```python
from dataclasses import dataclass
from equivalib.core import Extension, generate
from equivalib.core.expression import Expression
from typing import Iterator

@dataclass(frozen=True)
class Greeting(Extension):
    text: str

    @staticmethod
    def initialize(tree: object, constraint: Expression) -> None:
        del tree, constraint

    @staticmethod
    def enumerate_all(tree: object, constraint: Expression, address: str | None) -> Iterator["Greeting"]:
        del tree, constraint, address
        yield Greeting("hello")
        yield Greeting("hi")

    @staticmethod
    def arbitrary(tree: object, constraint: Expression, address: str | None) -> "Greeting | None":
        del tree, constraint, address
        return Greeting("hello")

    @staticmethod
    def uniform_random(tree: object, constraint: Expression, address: str | None) -> "Greeting | None":
        del tree, constraint, address
        return Greeting("hi")

greetings = generate(Greeting)
# => {Greeting("hello"), Greeting("hi")}
```

Any class can become a generation leaf by implementing the four `Extension` hooks.

---

## Slide 15 — LineIntervalsSet: non-equivalent interval families

```python
from equivalib.core import LineIntervalsSet, generate

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

representatives = generate(PairsUpTo5)
# => 4 representatives, one per equivalence class:
#    touch   – one interval ends exactly where the other begins, e.g. ([0,1], [1,2])
#    kiss    – endpoints differ by exactly 1, e.g. ([0,0], [1,1])
#    overlap – intervals share a non-degenerate interior, e.g. ([0,2], [1,3])
#    disjoint – no interaction at all, e.g. ([0,0], [2,2])
```

`LineIntervalsSet` enumerates exactly one representative from every equivalence class of
*n* integer line intervals, where two sets are equivalent when one is a permutation of
the other with the same pairwise relations (touch / kiss / overlap / disjoint).

---

## Slide 16 — Testing strategy in this repository

- Each interesting slide example has a corresponding executable test.
- Constraints are expressed using AST nodes (`Eq`, `And`, `Add`, ...), not strings.
- Addressing into named tuples uses `reference("Label", index, ...)`.
- `LineIntervalsSet` replaces hand-written equivalence-class enumeration loops in tests.

This keeps examples both educational and regression-safe.

---

## Slide 17 — Takeaway

- Start small (`bool` and tuples).
- Move from post-filters to explicit constraints with `reference`.
- Add domain-specific extensions (`Regex`, `LineIntervalsSet`, or custom `Extension`).
- Use SAT-backed constraints and witness modes for large integer domains.

All examples above are mirrored in `tests/test_interesting.py`.

