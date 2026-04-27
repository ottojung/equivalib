# Equivalib: Constraint-Driven Test Case Generation

## Slide 1 — Why this library exists

- Most test failures come from **interactions**, not isolated values.
- Handwritten fixtures miss combinations.
- `equivalib` generates concrete cases from declarative models.

---

## Slide 2 — Easiest start: one boolean

```python
from equivalib.core import generate

values = generate(bool)
# => {False, True}
```

---

## Slide 3 — Next: a tuple of booleans

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

---

## Slide 4 — Direct indexing on generated values

```python
from equivalib.core import generate

values = generate(tuple[bool, bool])
only_true_first = {item for item in values if item[0]}
# => {(True, False), (True, True)}
```

---

## Slide 5 — Extension example: finite regex language

```python
from equivalib.core import Regex, generate

class TicketCode(Regex):
    @staticmethod
    def expression() -> str:
        return r"(AB|CD)\d{2}"

codes = generate(TicketCode)
# => 200 values: AB00..AB99 and CD00..CD99
```

---

## Slide 6 — SAT example: Pythagorean triples in a large integer domain

```python
triples = generate_pythagorean_triples(limit=30)
# includes (3, 4, 5), (5, 12, 13), (20, 21, 29), ...
```

`generate_pythagorean_triples` is implemented with core integer constraints and direct tuple-path indexing (`T[0]`, `T[1]`, `T[2]`) so SAT performs the search.

---

## Slide 7 — Large domain, one canonical witness

```python
values = generate_sum_to_hundred_witness()
# => exactly one tuple witness with sum(value) == 100
```

This demonstrates the practical exhaustive-vs-canonical tradeoff on a huge constrained space.

---

## Slide 8 — Takeaway

- Start small (`bool` → tuples).
- Add realistic domains (regex).
- Use SAT-backed constraints for hard spaces (Pythagorean triples, constrained sums).
- Keep every example executable in tests.

All examples above are mirrored in `tests/test_interesting.py`.
