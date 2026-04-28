# Spec 1: Core Generate Semantics

## Purpose

This document specifies the core semantics of the library as a single generation interface over finite type trees, named values, and one boolean constraint.

This document defines the built-in core leaf language.
The planned extension mechanism for custom leaves and built-in overrides is specified separately in [extensions.md](extensions.md).

The core is defined by observable behavior.

It does not require any specific internal architecture. A compliant implementation MAY use staged expansion, direct search, dynamic programming, or some other implementation strategy.

The purpose of the core is to separate:

- structural possibility
- symbolic identity
- logical restriction
- witness-selection strategy

Those are distinct concepts and MUST remain distinct in compliant implementations.

## Scope

The core MUST support:

- finite boolean domains
- finite bounded integer domains via `ValueRange`
- literal values
- tuples
- unions
- named subtrees via `Name(label)`
- boolean constraint ASTs over labels and addresses
- one public generation function

Optional extension-owned leaves are outside the scope of this base document and are specified in [extensions.md](extensions.md).

The core does not specify:

- compilation from any other representation
- dataclass-specific behavior
- a particular AST representation language beyond the constructors in this spec

## Normative Terms

The words MUST, MUST NOT, SHOULD, SHOULD NOT, and MAY are to be interpreted as normative requirements.

## Core Interface

```python
Label: TypeAlias = str
Method: TypeAlias = Literal["all", "arbitrary", "uniform_random"]
Expression: TypeAlias = Union[
    BooleanConstant, IntegerConstant, Reference,
    Neg, Add, Sub, Mul, FloorDiv, Mod,
    Eq, Ne, Lt, Le, Gt, Ge,
    And, Or,
]

generate(tree: Type[T], constraint: Expression = BooleanExpression(True), methods: Optional[Mapping[Label, Method]] = None) -> Set[T]
```

The extension-aware superset of this interface adds an optional `extensions` registry; see [extensions.md](extensions.md).

Here `T` is the runtime type denoted by `tree`.

Default behavior:

- if `methods` is `None` or a label is not present in `methods`, its method is `"all"`
- if the constraint is omitted in examples, it defaults to `BooleanExpression(True)`

`BooleanExpression(True)` denotes the always-true boolean expression value. A compliant implementation MAY represent it canonically as `BooleanConstant(True)`.

There is only one constraint parameter because conjunction is already an AST constructor:

- `And(left, right)` combines constraints
- `BooleanExpression(True)` is the unconstrained case

Examples in this document MAY omit trailing default arguments. Therefore:

```python
generate(tree)
```

means:

```python
generate(tree, BooleanExpression(True), None)
```

When the extension-aware surface is used, omitted examples in this document should also be read as omitting the `extensions` argument.

## TypeTree

### Canonical syntax

The core is specified in terms of these conceptual constructors:

```text
TypeTree :=
    None
  | bool
  | Literal[value]
  | Tuple[t1, t2, ..., tn]
  | Union[t1, t2, ..., tn]
  | Annotated[base, metadata1, metadata2, ..., metadatan]

metadata :=
    ValueRange(min, max)
  | Name(label)
```

The extension-aware surface may add additional extension-owned leaves to this grammar; see [extensions.md](extensions.md).

The canonical constraints on `Annotated[...]` are:

- it MAY contain at most one `ValueRange(...)`
- it MAY contain at most one `Name(...)`
- if it contains `ValueRange(min, max)`, then `base` MUST be `int`
- every integer leaf MUST be finitely bounded, either directly (for example via
  `ValueRange(min, max)`) or via numeric constraints on a valid `Reference(label, path)`
  that points to that leaf
- `label` MUST be a string; the empty string `""` is only permitted when `base` is the
  root of the entire type tree (the outermost `Annotated` expression)
- a `Name(label)` that is not at the root MUST use a non-empty label

The value space is finite by construction.

Integer bounds are about the referenced leaf, not about whether the leaf itself
has a `Name(...)`. For example, in `Annotated[Tuple[int, int], Name("T")]`,
`Reference("T", (0,))` and `Reference("T", (1,))` MAY provide the required
bounds for both integer components.

### Examples of valid trees

```python
bool
Tuple[bool, Literal["N\\A"]]
Annotated[int, ValueRange(-5, 7)]
Tuple[Union[bool, None], Annotated[int, ValueRange(3, 9)]]
Annotated[bool, Name("X")]
Annotated[int, ValueRange(3, 9), Name("X")]
Annotated[Tuple[bool, bool], Name("X")]
Tuple[Annotated[bool, Name("X")], Annotated[bool, Name("Y")]]
Annotated[bool, Name("")]                       # root label: valid at outermost position
Annotated[Tuple[bool, bool], Name("")]          # root label wrapping a tuple
```

### Named occurrences

A named occurrence is any subtree of the form:

```text
Annotated[base, ..., Name(label), ...]
```

`Name(label)` defines variable identity.

The core MUST satisfy all of the following:

- two occurrences with the same label denote the same logical variable
- two occurrences with different labels denote different logical variables
- an implementation MUST NOT merge two different labels merely because their underlying domains are equal

Repeated labels are allowed.

If the same label appears more than once, the effective domain of that label is the intersection of the denotations of all of its occurrences.

## Super Values

A super value is not a syntactic category of `TypeTree`.

It is a semantic category induced by the chosen method.

Let `method(L)` be the effective method of label `L`, after defaulting missing entries to `"all"`.

Then:

- a label `L` is exhaustive iff `method(L) == "all"`
- a label `L` is super iff `method(L) != "all"`
- a named occurrence carrying a super label is a super occurrence

Intuition:

- exhaustive labels remain in full finite superposition until the final result set is formed
- super labels are collapsed to one witness value during generation

This terminology is conceptual. An implementation does not need a dedicated runtime type called `SuperValue`, but it MUST behave as if super labels are collapsed and exhaustive labels are not.

### Consequences of being super

If a label is super, the generator MUST choose one witness value for that label according to its method.

If a label is exhaustive, the generator MUST preserve all satisfying variation of that label.

The choice of whether a value is super therefore depends on `methods`, not on the tree syntax.

## Structural Equality and Sets

All results in this spec are mathematical sets.

Therefore:

- duplicates MUST be removed by structural equality
- output ordering is not observable
- union branch order is not observable
- tuple element order remains semantically significant

### bool and int are disjoint types

`bool` and `int` are disjoint types in this spec.

Even though Python's `bool` is a subclass of `int`, this spec treats them as entirely separate domains.

This means:

- `True != 1` and `False != 0` for all purposes of this spec
- a label whose domain is `bool` MUST NOT produce `int` values, and vice versa
- `Eq(x, y)` returns `False` whenever `x` is a boolean and `y` is an integer, regardless of their numeric values
- `Ne(x, y)` returns `True` whenever `x` is a boolean and `y` is an integer, regardless of their numeric values
- the same rule applies recursively inside tuples: `(True,) != (1,)`

A compliant implementation MUST enforce type-aware structural equality at every nesting level, so that boolean and integer values of the same magnitude are never conflated.

## Validation Rules

A compliant implementation MUST reject invalid trees, including at least:

- `ValueRange(min, max)` with `min > max`
- `Name("")` used at a non-root position (i.e. inside a `Tuple`, `Union`, or nested `Annotated`)
- plain `int` without a `ValueRange(...)`
- `Annotated[...]` with more than one `ValueRange(...)`
- `Annotated[...]` with more than one `Name(...)`
- `methods` containing a label that does not appear in the tree (after index/root label
  translation — see "Index-Style and Root Labels" below)
- a constraint referring to a label that does not appear in the tree

The implementation MAY reject additional malformed inputs if they are outside this spec.

## Expression

### Expression is an AST

`Expression` is an abstract syntax tree, not source text.

The core neither requires nor assumes parsing.

### Canonical constructors

The conceptual AST is:

```text
Expression :=
    BooleanConstant(value)
  | IntegerConstant(value)
  | Reference(label, path)
  | Neg(expr)
  | Add(left, right)
  | Sub(left, right)
  | Mul(left, right)
  | FloorDiv(left, right)
  | Mod(left, right)
  | Eq(left, right)
  | Ne(left, right)
  | Lt(left, right)
  | Le(left, right)
  | Gt(left, right)
  | Ge(left, right)
  | And(left, right)
  | Or(left, right)
```

Where:

- `value` is a boolean or integer constant
- `label` is either a `Label` or `None` (root reference)
- `path` is a finite tuple of zero-based tuple indices (`0` = first element, `1` = second, etc.)

Examples:

```python
Reference("X", ())
Reference("X", (0,))
Reference(None, (1, 0))
reference("X")
reference("X", 0)
reference(1, 0)
Eq(Reference("X", ()), Reference("Y", ()))
And(Lt(Reference("X", ()), Reference("Y", ())), Gt(Reference("X", ()), IntegerConstant(0)))
Or(
    And(Lt(Reference("X", ()), Reference("Y", ())), Gt(Reference("X", ()), IntegerConstant(0))),
    Lt(Reference("X", ()), IntegerConstant(0)),
)
```

### Type rules

- `Add`, `Sub`, `Mul`, `FloorDiv`, and `Mod` apply only to integers
- `Lt`, `Le`, `Gt`, and `Ge` apply only to integers
- `Eq` and `Ne` apply by structural equality to booleans, integers, `None`, strings, and tuples thereof
- `And` and `Or` apply only to booleans
- `Neg` applies only to integers

### Addressing

`Reference(label, path)` means:

- if `label is None`, start from the root generated value; otherwise start from the assigned runtime value of `label`
- then follow the tuple indices in `path`

Address evaluation MUST fail if any step:

- indexes a non-tuple value, or
- uses a negative index, or
- uses an out-of-range index

### Mentioned labels

Define `mentioned_labels(expr)` recursively as the set of non-`None` labels occurring in `Reference(label, path)` nodes.

This notion is used later when defining which labels must participate in constraint solving.

## Index-Style and Root Labels

### Root label

The empty string `""` is reserved as the **root label**.

When `methods` contains the key `""` and the tree has no existing `Name(...)` labels, a
compliant implementation MUST treat the whole root type as if it were wrapped in
`Annotated[tree, Name("")]`.  That is, the root value is assigned the label `""` and the
method `methods[""]` is applied to it as a unit.

All `Reference(None, path)` expressions in the constraint are implicitly rewritten to
`Reference("", path)` under this convention.

The user MAY also make the root label explicit by writing `Annotated[base, Name("")]`.
A `Name("")` annotation is only valid when it appears at the outermost (root) position of
the type tree; using it at any inner position MUST be rejected.

### Index-style labels

For an unnamed `Tuple[t0, t1, ..., t_{n-1}]` root, each element `i` carries the
**index-style label** `f"[{i}]"` (for example `"[0]"`, `"[1]"`, `"[9]"`, etc.).

When `methods` contains any key of the form `"[i]"` and the root is an unnamed
`Tuple`, a compliant implementation MUST:

1. Treat element `i` as if it were wrapped in `Annotated[t_i, Name("[i]")]`.  Elements
   that are not mentioned in `methods` also receive virtual labels (for constraint
   rewriting purposes) and default to method `"all"`.
2. Rewrite every `Reference(None, (i, *rest))` in the constraint to
   `Reference("[i]", rest)` before validation and solving.

This rewriting allows `reference(i)` (the short form `Reference(None, (i,))`) to address
individual elements of an unnamed tuple by index, while still applying per-element methods.

A method key `"[i]"` where `i` is out of range for the tuple MUST be rejected as an
unknown label.

### Priority rule

Combining root and index labels on the same unnamed tuple root is invalid.

If the root is a `Tuple` and `methods` contains any index-style key `"[i]"`,
the root label `""` MUST NOT also be present in `methods`.  A compliant implementation
MUST reject this combination with a `ValueError`.

If `methods` contains only index-style keys (no `""`), index-style label translation is
applied: each tuple element `i` is wrapped in `NamedNode(f"[{i}]", ...)`.

If `methods` contains only `""` (no index-style keys), or if the root is not a `Tuple`,
the whole root is wrapped in `NamedNode("", ...)`.

If the root is not a `Tuple`, index-style keys are invalid labels and MUST be rejected.


## Denotation of Unnamed Trees

The core needs a finite denotation for every name-free subtree.

Define `values(t)` for trees that contain no `Name(...)` metadata.

```text
values(None)
  = { None }

values(bool)
  = { True, False }

values(Literal[v])
  = { v }

values(Annotated[int, ValueRange(min, max)])
  = { min, min + 1, ..., max }

values(Union[t1, t2, ..., tn])
  = values(t1) union values(t2) union ... union values(tn)

values(Tuple[t1, t2, ..., tn])
  = {
      (v1, v2, ..., vn)
      | v1 in values(t1),
        v2 in values(t2),
        ...,
        vn in values(tn)
    }
```

If a tree is name-free, then:

```text
generate(tree, BooleanExpression(True), {}) == values(tree)
```

## Effective Label Domains

For each named occurrence of label `L`, remove only the `Name(L)` metadata and call the resulting name-free subtree the occurrence-domain tree.

The effective domain of label `L` is:

```text
domain(L) = intersection(values(occurrence_domain_tree_i) for every occurrence i of label L)
```

Consequences:

- if a label occurs once, its domain is the denotation of that one occurrence
- if a label occurs several times, all occurrences must agree on one shared value
- if the intersection is empty, then `generate(...)` MUST return `{}`

### Example

```text
Tuple[
  Annotated[int, ValueRange(1, 5), Name("X")],
  Annotated[int, ValueRange(3, 7), Name("X")]
]
```

has:

```text
domain("X") = { 3, 4, 5 }
```

## Satisfying Assignments

Let `labels(tree)` be the set of labels used in the tree.

A candidate assignment `σ` maps every label in `labels(tree)` to one concrete runtime value.

An assignment is admissible if:

- for every label `L`, `σ(L)` is in `domain(L)`
- `constraint` evaluates to `True` under `σ`

Let:

```text
Sat(tree, constraint)
```

denote the set of all admissible assignments.

If `Sat(tree, constraint)` is empty, then:

```text
generate(tree, constraint, methods) == {}
```

for every method configuration.

## Concretization Under an Assignment

For an admissible assignment `σ`, define `concretize(tree, σ)` as the set of runtime objects obtained by recursively interpreting the tree with labels replaced by `σ`.

```text
concretize(None, σ)
  = { None }

concretize(bool, σ)
  = { True, False }

concretize(Literal[v], σ)
  = { v }

concretize(Annotated[int, ValueRange(min, max)], σ)
  = { min, min + 1, ..., max }

concretize(Union[t1, t2, ..., tn], σ)
  = concretize(t1, σ) union concretize(t2, σ) union ... union concretize(tn, σ)

concretize(Tuple[t1, t2, ..., tn], σ)
  = {
      (v1, v2, ..., vn)
      | v1 in concretize(t1, σ),
        v2 in concretize(t2, σ),
        ...,
        vn in concretize(tn, σ)
    }

concretize(Annotated[base, ..., Name(L), ...], σ)
  = { σ(L) }
```

In other words:

- unnamed structure still expands normally
- named occurrences are replaced atomically by the assigned value for their label

## Method Semantics

### Overview

Methods control which labels remain exhaustive and which collapse to a singleton witness.

- `"all"` means do not pre-fix that label
- every other method chooses exactly one witness value for that label

Unnamed structure is never affected by methods. It always expands fully.

### Processing order

Let:

```text
S0 = Sat(tree, constraint)
```

If `S0` is empty, the result is `{}`.

Otherwise, let `S := S0` and process every super label in **structural tree order**: the order in which labels first appear during a left-to-right depth-first traversal of `tree`.

For example, in `Tuple[Annotated[bool, Name("A")], Annotated[bool, Name("B")]]`, label `"A"` is encountered before `"B"`, so `"A"` is processed first regardless of alphabetic or any other ordering.

This ordering is based on the *position* of the label in the tree, not on its string name.  This guarantees **alpha-conversion invariance**: consistently renaming all occurrences of a label cannot change the processing order, and therefore cannot change the output set.

For any current assignment set `S` and label `L`, define:

```text
projection(L, S) = { σ(L) | σ in S }
```

Since `S` is non-empty while processing continues, every such projection is non-empty.

### Method `"all"`

`"all"` does not filter assignments.

It exists to preserve the full satisfying variation of that label.

This method MUST be deterministic.

### Method `"arbitrary"`

For label `L`, choose one value:

```text
v = select_arbitrary(L, S)
```

such that:

- `v` is in `projection(L, S)`
- the selection is deterministic for fixed input
- `v` is the first element of `projection(L, S)` under canonical value order

Canonical value order is:

1. `None`
2. booleans (`False < True`)
3. integers in ascending numeric order
4. strings in ascending lexicographic order
5. tuples in ascending lexicographic order under this same recursive value order

Then replace `S` by:

```text
{ σ in S | σ(L) = v }
```

This method prioritizes speed and witness production.

It MUST be deterministic.

It MUST satisfy this non-emptiness invariant:

- if `S0` is non-empty, applying `"arbitrary"` MUST NOT make the result empty

### Method `"uniform_random"`

For label `L`, choose one value `v` from `projection(L, S)` with probability:

```text
P(v) = |{ σ in S | σ(L) = v }| / |S|
```

Then replace `S` by:

```text
{ σ in S | σ(L) = v }
```

This method MUST be non-deterministic.

It MUST satisfy this non-emptiness invariant:

- if `S0` is non-empty, applying `"uniform_random"` MUST NOT make the result empty

If every label is super and every super label uses `"uniform_random"`, then the final singleton assignment MUST be uniformly distributed over the satisfying assignments in `S0`, modulo deduplication of equal runtime outputs.

## Definition of `generate`

Let `S*` be the assignment set that remains after processing every super label according to its method.

Then:

```text
generate(tree, constraint, methods)
  = union(concretize(tree, σ) for every σ in S*)
```

This definition implies the key invariant:

- a super method MUST return a non-empty result if and only if the corresponding all-exhaustive problem is non-empty

Methods may change completeness, determinism, and distribution, but they MUST NOT introduce emptiness when satisfying assignments already exist.

## Precise Input→Output Semantics

### High-level description

`generate(tree, constraint, methods)` returns the set of all concrete Python values of the type denoted by `tree` that can be produced by at least one satisfying assignment after applying the chosen witness-selection methods.

Intuitively:

1. The tree defines the *shape* of the output and the *domains* of named labels.
2. The constraint filters which combinations of label values are admissible.
3. Each method decides whether a label contributes all of its admissible variation to the output (`"all"`) or is collapsed to a single canonical witness (`"arbitrary"`, `"uniform_random"`).
4. The output is the union of all concrete values produced by every remaining admissible assignment.

Named labels are the variables of the system.  Unnamed subtrees always expand exhaustively.

### Mathematical formulation

**Input:**

- `tree` — a `TypeTree` expression (from the TypeTree grammar in this document)
- `constraint` — an `Expression` AST node
- `methods` — a partial map from `Label` to `Method`; missing labels default to `"all"`

**Output:**

- A finite set `R ⊆ 𝒱`, where `𝒱` is the set of all runtime Python values

**Notation:** let `𝒱(t)` denote `values(t)` (the denotation of an unnamed tree `t`).

**Step 1 — Labels and domains.**

Let `L = labels(tree)` be the set of labels in the tree.

For each label `ℓ ∈ L`, let:

```text
domain(ℓ) = ⋂ { values(occurrence-domain(ℓ, i)) | i is an occurrence of ℓ in tree }
```

where `occurrence-domain(ℓ, i)` is the tree obtained by stripping `Name(ℓ)` from the `i`-th named occurrence.

**Step 2 — Satisfying assignments.**

A *candidate assignment* is a total function `σ : L → 𝒱` such that:

- for every `ℓ ∈ L`: `σ(ℓ) ∈ domain(ℓ)`
- `eval(constraint, σ) = True`

Let `S0` be the set of all candidate assignments:

```text
S0 = { σ : L → 𝒱 | (∀ ℓ ∈ L. σ(ℓ) ∈ domain(ℓ)) ∧ eval(constraint, σ) = True }
```

If `S0 = ∅` then `R = ∅` and generation is complete.

**Step 3 — Method application.**

Let `super_labels` be the labels with a non-`"all"` method, ordered by their first-appearance position in `tree` (structural tree order).

Let `S := S0`.

For each `ℓ ∈ super_labels` in structural order:

```text
v  = method_select(method(ℓ), ℓ, S)
S  = { σ ∈ S | σ(ℓ) = v }
```

where `method_select` is defined by the method:

- `"arbitrary"`: `v` is the canonical minimum of `{ σ(ℓ) | σ ∈ S }` under canonical value order
- `"uniform_random"`: `v` is sampled from `{ σ(ℓ) | σ ∈ S }` weighted by how many assignments support each value

Let `S*` be the value of `S` after all super labels have been processed.

**Step 4 — Concretization.**

```text
R = ⋃ { concretize(tree, σ) | σ ∈ S* }
```

**Structural order (alpha-conversion invariance).**

Super labels are processed in the order they first appear during a left-to-right depth-first traversal of `tree`.  This order is a property of the *tree structure*, not of the label strings.  Therefore:

> Consistently renaming all occurrences of any label (alpha conversion) MUST NOT change the output set `R` for deterministic selection methods such as `"all"` and `"arbitrary"`.
>
> For `"uniform_random"`, alpha conversion MUST NOT change the set of possible outputs or the sampling distribution induced by the same implementation. It does not require identical sampled outputs across runs unless the RNG seed and implementation-defined iteration order are held fixed.

A compliant implementation MUST guarantee this invariance at the appropriate semantic level for the selected method.

**Full formula.**

Combining all steps:

```text
generate(tree, constraint, methods)
  = ⋃ { concretize(tree, σ)
        | σ ∈ reduce_by_methods(Sat(tree, constraint), methods, structural_order(tree)) }
```

where:

- `Sat(tree, constraint)` is the set of all admissible assignments as defined in Step 2
- `reduce_by_methods` applies each super label's method in structural tree order as defined in Step 3
- `concretize` is defined in the "Concretization Under an Assignment" section



The `"all"` examples below are exact.

The examples using `"arbitrary"` or `"uniform_random"` show one compliant outcome unless stated otherwise.

```python
generate(Literal[True], BooleanExpression(True), {})
== { True }

generate(Tuple[bool, Literal["N\\A"]], BooleanExpression(True), {})
== { (True, "N\\A"), (False, "N\\A") }

generate(Annotated[bool, Name("X")], BooleanExpression(True), {"X": "all"})
== { True, False }

generate(Annotated[bool, Name("X")], BooleanExpression(True), {"X": "arbitrary"})
== { False }

generate(Annotated[Tuple[bool, bool], Name("X")], BooleanExpression(True), {"X": "arbitrary"})
== { (False, False) }

generate(
    Tuple[Annotated[bool, Name("X")], Annotated[bool, Name("Y")]],
    Eq(Reference("X", ()), Reference("Y", ())),
  {"X": "all", "Y": "all"},
)
== { (True, True), (False, False) }

generate(
    Tuple[Annotated[bool, Name("X")], Annotated[bool, Name("Y")]],
    Ne(Reference("X", ()), Reference("Y", ())),
  {"X": "all", "Y": "all"},
)
== { (True, False), (False, True) }

generate(
    Tuple[Annotated[bool, Name("X")], Annotated[bool, Name("Y")]],
    Eq(Reference("X", ()), Reference("Y", ())),
  {"X": "all", "Y": "arbitrary"},
)
== { (False, False) }

generate(
    Tuple[Annotated[bool, Name("X")], Annotated[bool, Name("Y")]],
    Ne(Reference("X", ()), Reference("Y", ())),
  {"X": "all", "Y": "arbitrary"},
)
== { (True, False) }

generate(
    Tuple[Annotated[bool, Name("X")], Annotated[bool, Name("Y")]],
    Ne(Reference("X", ()), Reference("Y", ())),
  {"X": "arbitrary", "Y": "arbitrary"},
)
== { (False, True) }

generate(
    Annotated[Tuple[bool, bool], Name("X")],
    Ne(Reference("X", (0,)), Reference("X", (1,))),
  {"X": "all"},
)
== { (True, False), (False, True) }
```

## Compliance

A core implementation is compliant with this spec if it:

- accepts valid inputs covered by this document
- rejects invalid inputs covered by this document
- implements the denotation of unnamed trees correctly
- implements label-domain intersection correctly
- evaluates `Expression` ASTs according to the constructor semantics above
- implements super-label semantics and the non-emptiness invariant correctly
- returns plain runtime values as a set of instances of the denoted runtime type

For randomized methods, compliance has two layers:

- MUST-level shape guarantees
- SHOULD-level distribution-quality guarantees

### Compliance matrix

| ID | Level | Requirement | Input / Operation | Expected result |
| --- | --- | --- | --- | --- |
| GEN-01 | MUST | Literal generation | `generate(Literal[True], BooleanExpression(True), {})` | `{True}` |
| GEN-02 | MUST | Unnamed tuple expansion | `generate(Tuple[bool, Literal["N\\A"]], BooleanExpression(True), {})` | `{(True, "N\\A"), (False, "N\\A")}` |
| GEN-03 | MUST | Bounded integer expansion | `generate(Annotated[int, ValueRange(3, 4)], BooleanExpression(True), {})` | `{3, 4}` |
| GEN-04 | MUST | Default method is `"all"` | `generate(Annotated[bool, Name("X")], BooleanExpression(True), {})` | `{True, False}` |
| GEN-05 | MUST | Same label means same value | `generate(Tuple[Annotated[bool, Name("X")], Annotated[bool, Name("X")]], BooleanExpression(True), {"X": "all"})` | `{(True, True), (False, False)}` |
| GEN-06 | MUST | Equality constraint with exhaustive methods | `generate(Tuple[Annotated[bool, Name("X")], Annotated[bool, Name("Y")]], Eq(Reference("X", ()), Reference("Y", ())), {"X": "all", "Y": "all"})` | `{(True, True), (False, False)}` |
| GEN-07 | MUST | Inequality constraint with exhaustive methods | `generate(Tuple[Annotated[bool, Name("X")], Annotated[bool, Name("Y")]], Ne(Reference("X", ()), Reference("Y", ())), {"X": "all", "Y": "all"})` | `{(True, False), (False, True)}` |
| GEN-08 | MUST | Address constraints work | `generate(Annotated[Tuple[bool, bool], Name("X")], Ne(Reference("X", (0,)), Reference("X", (1,))), {"X": "all"})` | `{(True, False), (False, True)}` |
| GEN-09 | MUST | Repeated label domains intersect | `generate(Tuple[Annotated[int, ValueRange(1, 5), Name("X")], Annotated[int, ValueRange(3, 7), Name("X")]], BooleanExpression(True), {"X": "all"})` | `{(3, 3), (4, 4), (5, 5)}` |
| GEN-10 | MUST | Impossible constraints produce empty output | `generate(Tuple[Annotated[bool, Name("X")], Annotated[bool, Name("Y")]], And(Eq(Reference("X", ()), Reference("Y", ())), Ne(Reference("X", ()), Reference("Y", ()))), {"X": "all", "Y": "all"})` | `{}` |
| GEN-11 | MUST | `arbitrary` is a singleton subset of the `"all"` result when satisfiable | compare `generate(tree, constraint, {"X": "arbitrary"})` against `generate(tree, constraint, {"X": "all"})` | result cardinality is `1`, result is a subset of the `"all"` result |
| GEN-12 | MUST | `arbitrary` is deterministic | run the same `generate(...)` call with `"arbitrary"` repeatedly | same result every time |
| GEN-13 | MUST | Super methods preserve non-emptiness | for any satisfiable input, replace some `"all"` methods with super methods | output stays non-empty |
| GEN-14 | MUST | `uniform_random` returns a singleton subset of the `"all"` result when satisfiable | compare `generate(tree, constraint, {"X": "uniform_random"})` against `generate(tree, constraint, {"X": "all"})` | result cardinality is `1`, result is a subset of the `"all"` result |
| GEN-15 | SHOULD | `uniform_random` is statistically close to uniform when all labels are super and use `"uniform_random"` | sample many runs on a problem with several satisfying assignments | frequencies are close to uniform over satisfying outputs |
| GEN-16 | MUST | Empty label is invalid | any tree containing `Name("")` | validation error |
| GEN-17 | MUST | Missing label reference in the expression is invalid | `generate(Annotated[bool, Name("X")], Eq(Reference("Y", ()), BooleanConstant(True)), {})` | validation error |
| GEN-18 | MUST | Plain `int` is invalid in core | any tree containing plain `int` without `ValueRange(...)` | validation error |
| GEN-19 | MUST | `Expression` is AST-based, not source-text-based | pass a source string instead of an AST | type or validation error |
| GEN-20 | MUST | Single-constraint conjunction replaces a constraint set | compare `generate(tree, And(c1, c2), methods)` with the conceptual two-constraint case | same result as requiring both `c1` and `c2` |
| GEN-21 | MUST | `bool` and `int` are disjoint: `Eq(bool_val, int_val)` is false | `generate(Tuple[Annotated[bool, Name("X")], Annotated[int, ValueRange(1, 1), Name("Y")]], Eq(Reference("X", ()), Reference("Y", ())), {"X": "all", "Y": "all"})` | `{}` |
| GEN-22 | MUST | `bool` and `int` are disjoint: `Ne(bool_val, int_val)` is true | `generate(Tuple[Annotated[bool, Name("X")], Annotated[int, ValueRange(1, 1), Name("Y")]], Ne(Reference("X", ()), Reference("Y", ())), {"X": "all", "Y": "all"})` | `{(True, 1), (False, 1)}` |

## Summary

This core has one observable interface:

```python
generate(tree, constraint, methods)
```

Its semantics are governed by four ideas:

- unnamed structure expands exhaustively
- `Name(label)` defines variable identity
- `Expression` restricts admissible assignments
- super methods collapse selected labels to one witness

The key invariant is the one that motivated this redesign:

- methods may change completeness, determinism, and distribution
- but they MUST NOT make a satisfiable problem empty

That property is part of compliance.
