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
only_true_first = {item for item in values if item[0] != item[1]}
# => {(False, True), (True, False)}
```

Great for demos, quick checks, and building intuition.

---

## Slide 5 — In-model constraints via string expressions

```python
from equivalib.core import generate

tree = tuple[bool, bool]

values = generate(tree, "[0] != [1]")
# => {(False, True), (True, False)}
```

Instead of filtering after generation, we encode relationships directly into the solver input.
The constraint string `"[0] != [1]"` means "the first element must not equal the second".

---

## Slide 5b — String syntax: named trees

```python
from typing import Annotated
from equivalib.core import Ne, generate, reference, Name

tree = tuple[bool, bool]
constraint = Ne(reference(0), reference(1))

values = generate(tree, constraint, {"B": "all"})
# => {(False, True), (True, False)}
```

The `ParsedExpression` AST form is also accepted — strings and AST nodes are interchangeable.

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

values = generate(Union[Literal[2, 3, 4], bool])
# => {False, True, 2, 3, 4}
```

Union deduplicates across branches using normal Python set semantics (hash/equality).

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
from equivalib.core import generate

def generate_pythagorean_triples(limit: int):
    tree = tuple[int, int, int]
    bounds = (
        f"[0] >= 1 and [0] <= {limit} and "
        f"[1] >= 1 and [1] <= {limit} and "
        f"[2] >= 1 and [2] <= {limit}"
    )
    ordered     = "[0] <= [1] and [1] <= [2]"
    pythagorean = "[0] * [0] + [1] * [1] == [2] * [2]"
    return generate(tree, f"({bounds}) and ({ordered}) and ({pythagorean})")

triples = generate_pythagorean_triples(limit=30)
# includes (3, 4, 5), (5, 12, 13), (20, 21, 29), ...
```

SAT-backed integer constraints scale to large search spaces with precise semantics.
The same constraint can also be written as a `ParsedExpression` AST for programmatic construction.

---

## Slide 11 — Canonical witness on huge spaces

```python
values = generate_sum_to_hundred_witness()
# => exactly one tuple witness (10 binary values summing to 5)
```

Using `{"[0]": "arbitrary", "[1]": "arbitrary", ...}` asks for one deterministic witness instead of exhaustive enumeration.

---

## Slide 12 — Mixing generation modes per label

```python
from typing import Annotated
from equivalib.core import generate, Name

tree = tuple[Annotated[int, Name("X")], Annotated[int, Name("Y")]]

result = generate(
    tree,
    "X >= 0 and X <= 9 and Y >= 0 and Y <= 9 and X > Y",
    {"X": "all", "Y": "arbitrary"},
)
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
import random
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
        return random.choice([Greeting("hello"), Greeting("hi")])

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
- Constraints are expressed as strings (`"X == Y"`, `"[0] != [1]"`, ...) or as AST nodes (`Eq`, `And`, `Add`, ...).
- Addressing into named tuples uses `reference("Label", index, ...)` in AST form, or `Label[index]` in string form.
- `LineIntervalsSet` replaces hand-written equivalence-class enumeration loops in tests.

This keeps examples both educational and regression-safe.

---

## Slide 17 — Takeaway

- Start small (`bool` and tuples).
- Move from post-filters to explicit constraints with `reference`.
- Add domain-specific extensions (`Regex`, `LineIntervalsSet`, or custom `Extension`).
- Use SAT-backed constraints and witness modes for large integer domains.

All examples above are mirrored in `tests/test_interesting.py`.

