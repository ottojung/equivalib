# Equivalib: Constraint-Driven Test Case Generation

## Slide 1 — Why this library exists

- Most test failures come from **interactions**, not isolated values.
- Handwritten fixtures usually under-sample the real state space.
- `equivalib` lets you describe **what must hold**, then generates values that satisfy it.

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

## Slide 6 — Extension example: finite regex language

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

## Slide 7 — Realistic data slicing on generated extensions

```python
codes = generate(TicketCode)
ab_prefixed = {code for code in codes if str(code).startswith("AB")}

# len(ab_prefixed) == 100
# TicketCode("AB42") in ab_prefixed
# TicketCode("CD42") not in ab_prefixed
```

This pattern keeps generation declarative while still allowing business-level subsets.

---

## Slide 8 — SAT-backed integer relations: Pythagorean triples

```python
triples = generate_pythagorean_triples(limit=30)
# includes (3, 4, 5), (5, 12, 13), (20, 21, 29), ...
```

`generate_pythagorean_triples` uses integer constraints plus tuple-path references (`reference("T", 0/1/2)`).

---

## Slide 9 — Canonical witness on huge spaces

```python
values = generate_sum_to_hundred_witness()
# => exactly one tuple witness with sum(value) == 100
```

Using `{"X": "arbitrary"}` asks for one deterministic witness instead of exhaustive enumeration.

---

## Slide 10 — Practical generation modes

- `"all"`: exhaustive values (small/finite spaces).
- `"arbitrary"`: one canonical satisfying witness.
- `"uniform_random"`: one random satisfying witness.

Use per-label methods to mix exhaustive and witness-oriented generation.

---

## Slide 11 — Testing strategy in this repository

- Each interesting slide example has a corresponding executable test.
- Constraints are expressed using AST nodes (`Eq`, `And`, `Add`, ...), not strings.
- Addressing into named tuples uses `reference("Label", index, ...)`.

This keeps examples both educational and regression-safe.

---

## Slide 12 — Takeaway

- Start small (`bool` and tuples).
- Move from post-filters to explicit constraints with `reference`.
- Add domain-specific extensions (regex).
- Use SAT-backed constraints and witness modes for large integer domains.

All examples above are mirrored in `tests/test_interesting.py`.
