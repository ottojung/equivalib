# Interface-based Extensions for `equivalib.core.generate`

This document defines the extension design for custom class leaves in `equivalib.core.generate`.

## Scope

Extensions are discovered from the class itself via an interface implemented on the class.

Core leaf language remains built-in and unchanged for:

- `bool`
- `int` (named/bounded as defined in the core spec)
- `tuple[...]`
- `union` (`typing.Union[...]` / `|`)
- supported `Literal[...]` forms

For any class leaf outside that base language, generation checks whether that class implements the required extension interface below.

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

## Required Interface

When a non-base class leaf is encountered, its class must provide these static methods:

```python
@staticmethod
def initialize(tree: Type[T], constraint: Expression) -> Optional[Expression]:
    ...

@staticmethod
def enumerate_all(tree: Type[T], constraint: Expression, address: Optional[str]) -> Iterator[A]:
    ...

@staticmethod
def arbitrary(tree: Type[T], constraint: Expression, address: Optional[str]) -> Optional[A]:
    ...

@staticmethod
def uniform_random(tree: Type[T], constraint: Expression, address: Optional[str]) -> Optional[A]:
    ...
```

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
2. Otherwise if `L` is a class and that class implements the required static interface, that class owns the leaf.
3. Otherwise generation fails (unsupported leaf / missing interface).


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
- Reachable tuple child from addressable parent → dot path (e.g. `"X.0"`, `"0.1"`)
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

- a non-base class leaf does not implement the required interface,
- required interface methods are missing or non-callable,
- `initialize` returns a non-expression or non-boolean expression,
- hook outputs are inadmissible for the addressed occurrence,
- invalid expression operations are applied to atomic extension-owned leaves,
- exhaustive or uniform-random generation is requested for unsupported infinite domains.

---

## Examples

### Class-owned custom leaf

```python
import random


class Regex:
    @staticmethod
    def initialize(tree, constraint):
        return None

    @staticmethod
    def enumerate_all(tree, constraint, address):
        yield from ["ab", "cd"]

    @staticmethod
    def arbitrary(tree, constraint, address):
        return "ab"

    @staticmethod
    def uniform_random(tree, constraint, address):
        return random.choice(["ab", "cd"])
```

Then:

```python
generate(Regex)
generate(Annotated[Regex, Name("R")], methods={"R": "arbitrary"})
```

use `Regex`'s interface methods directly.
