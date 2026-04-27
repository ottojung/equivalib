# Equivalib: Constraint-Driven Test Case Generation

## Slide 1 — Why this library exists

- Most test failures hide in **interaction effects**, not in isolated inputs.
- Hand-written examples miss combinations; brute force explodes combinatorially.
- `equivalib` gives you:
  - a **type tree** for structure,
  - a **constraint AST** for validity,
  - and **selection methods** (`all`, `arbitrary`, `uniform_random`) for scale/performance trade-offs.

---

## Slide 2 — Mental model

Think of generation as four layers:

1. **Structure**: what values could exist (types, ranges, tuples, unions).
2. **Identity**: which fields are tied together (`Name("X")`).
3. **Logic**: which combinations are legal (`Eq`, `Le`, `And`, etc.).
4. **Selection strategy**: how many witnesses per label (`all` vs `arbitrary`).

---

## Slide 3 — Core API in one minute

```python
from typing import Annotated, Tuple
from equivalib.core import (
    generate, Name,
    BooleanExpression, IntegerConstant, Reference,
    And, Ge, Le, Lt,
)

# Generate values of a type tree that satisfy a boolean constraint:
result = generate(
    tree=Tuple[
        Annotated[int, Name("X")],
        Annotated[int, Name("Y")],
    ],
    constraint=And(
        And(Ge(Reference("X"), IntegerConstant(0)), Le(Reference("X"), IntegerConstant(3))),
        And(Ge(Reference("Y"), IntegerConstant(0)), Lt(Reference("X"), Reference("Y"))),
    ),
    methods={"X": "all", "Y": "all"},
)
```

Key point: output is a **set of concrete runtime values** satisfying both type and logic.

---

## Slide 4 — Example: shared labels = shared values

```python
from typing import Annotated, Tuple
from equivalib.core import generate, Name, BooleanExpression

tree = Tuple[
    Annotated[bool, Name("Flag")],
    Annotated[bool, Name("Flag")],
]

# Same label appears twice, so both positions must be equal.
values = generate(tree, BooleanExpression(True), {"Flag": "all"})
# => {(False, False), (True, True)}
```

Great for modeling “same user”, “same region”, “same feature gate”, etc.

---

## Slide 5 — Example: Regex generators (great demo slide)

```python
from equivalib.core import generate, Regex

class TicketCode(Regex):
    @staticmethod
    def expression() -> str:
        return r"(AB|CD)\d{2}"

codes = generate(TicketCode)
# Finite language: AB00..AB99 and CD00..CD99 (200 values)
```

Why this is presentation-friendly:

- Easy to explain (pattern -> concrete values).
- Visually compelling.
- Shows extension mechanism without changing core solver semantics.

---

## Slide 6 — The scaling story: `all` vs `arbitrary`

- `all`: keep exhaustive variability for that label.
- `arbitrary`: keep one canonical witness for that label.

This is the switch that prevents “nice model, impossible runtime” situations.

---

## Slide 7 — Big-domain example (huge expansion, tiny output)

```python
from typing import Annotated, Tuple
from equivalib.core import generate, Name, BooleanExpression

# 40 booleans => 2^40 potential assignments (>1 trillion)
Bool40 = Tuple[
    Annotated[bool, Name("B00")], Annotated[bool, Name("B01")],
    Annotated[bool, Name("B02")], Annotated[bool, Name("B03")],
    Annotated[bool, Name("B04")], Annotated[bool, Name("B05")],
    Annotated[bool, Name("B06")], Annotated[bool, Name("B07")],
    Annotated[bool, Name("B08")], Annotated[bool, Name("B09")],
    Annotated[bool, Name("B10")], Annotated[bool, Name("B11")],
    Annotated[bool, Name("B12")], Annotated[bool, Name("B13")],
    Annotated[bool, Name("B14")], Annotated[bool, Name("B15")],
    Annotated[bool, Name("B16")], Annotated[bool, Name("B17")],
    Annotated[bool, Name("B18")], Annotated[bool, Name("B19")],
    Annotated[bool, Name("B20")], Annotated[bool, Name("B21")],
    Annotated[bool, Name("B22")], Annotated[bool, Name("B23")],
    Annotated[bool, Name("B24")], Annotated[bool, Name("B25")],
    Annotated[bool, Name("B26")], Annotated[bool, Name("B27")],
    Annotated[bool, Name("B28")], Annotated[bool, Name("B29")],
    Annotated[bool, Name("B30")], Annotated[bool, Name("B31")],
    Annotated[bool, Name("B32")], Annotated[bool, Name("B33")],
    Annotated[bool, Name("B34")], Annotated[bool, Name("B35")],
    Annotated[bool, Name("B36")], Annotated[bool, Name("B37")],
    Annotated[bool, Name("B38")], Annotated[bool, Name("B39")],
]

one_witness = generate(
    Bool40,
    BooleanExpression(True),
    {f"B{i:02d}": "arbitrary" for i in range(40)},
)
# => exactly one canonical assignment instead of enumerating 2^40
```

Narration line: “Our model defines a trillion-state space, but `arbitrary` keeps generation operational by selecting one canonical satisfying witness per super label.”

---

## Slide 8 — Even better: huge domains + SAT constraints

```python
from typing import Annotated, Tuple
from equivalib.core import (
    generate, Name,
    Reference, IntegerConstant,
    Add, Eq, And, Ge, Le,
)

# 10 integer labels with 0..999 each => 1000^10 raw combos
Tree = Tuple[
    Annotated[int, Name("X0")], Annotated[int, Name("X1")], Annotated[int, Name("X2")],
    Annotated[int, Name("X3")], Annotated[int, Name("X4")], Annotated[int, Name("X5")],
    Annotated[int, Name("X6")], Annotated[int, Name("X7")], Annotated[int, Name("X8")],
    Annotated[int, Name("X9")],
]

bounds = And(
    And(Ge(Reference("X0"), IntegerConstant(0)), Le(Reference("X0"), IntegerConstant(999))),
    And(Ge(Reference("X1"), IntegerConstant(0)), Le(Reference("X1"), IntegerConstant(999))),
    # ... repeat for X2..X9
)

sum_100 = Eq(
    Add(Add(Add(Add(Add(Add(Add(Add(Add(
        Reference("X0"), Reference("X1")), Reference("X2")), Reference("X3")),
        Reference("X4")), Reference("X5")), Reference("X6")), Reference("X7")),
        Reference("X8")),
    Reference("X9")),
    IntegerConstant(100),
)

result = generate(
    Tree,
    And(bounds, sum_100),
    {f"X{i}": "arbitrary" for i in range(10)},
)
```

Why this is a strong slide:

- Raw domain is astronomically large.
- Constraint is global (sum coupling all variables).
- CP-SAT prunes infeasible regions; `arbitrary` avoids full enumeration.

---

## Slide 9 — What makes this robust for testing

- **Deterministic canonical ordering** for `arbitrary` selection.
- **Type-aware equality** (bool and int remain disjoint semantically).
- **Label reuse semantics** naturally encode aliases and consistency constraints.
- **Mixed strategy support**: exhaustive where needed, collapsed where expensive.

---

## Slide 10 — Practical adoption pattern

1. Start with a single high-value type tree.
2. Add constraints matching domain invariants.
3. Run with `all` on critical labels for breadth.
4. Switch low-value/high-cardinality labels to `arbitrary`.
5. Add regex/custom extensions for realistic leaf values (IDs, codes, tokens).

---

## Slide 11 — Demo plan (for live presentation)

1. Show `Regex` subclass -> finite generated language.
2. Show repeated `Name("X")` enforcing equality across fields.
3. Show huge constrained integer domain with CP-SAT.
4. Flip methods from `all` to `arbitrary` and compare output cardinality.

---

## Slide 12 — Takeaway

**equivalib lets you model very large test spaces declaratively, then choose the right exploration mode per label so generation remains practical without losing correctness.**

If you want, I can also draft:

- a 5-minute “lightning talk” version,
- speaker notes per slide,
- and a live-demo script with copy/paste-ready commands.
