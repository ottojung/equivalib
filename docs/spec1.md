# Spec 1: Core Generate Semantics

## Purpose

This document specifies the core semantics of the library as a single generation interface over finite type trees, named values, and one boolean constraint.

The core is defined by observable behavior.

It does not require any specific internal architecture. A compliant implementation MAY use staged expansion, direct search, dynamic programming, SAT-style solving, SMT-style solving, CP-SAT, or some other implementation strategy.

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
- well-defined semantic caching

The core does not specify:

- compilation from any other representation
- dataclass-specific behavior
- a particular AST representation language beyond the constructors in this spec
- a particular solver backend

## Normative Terms

The words MUST, MUST NOT, SHOULD, SHOULD NOT, and MAY are to be interpreted as normative requirements.

## Core Interface

```python
Label: TypeAlias = str
Method: TypeAlias = Literal["all", "arbitrary", "uniform_random", "arbitrarish_randomish"]

generate(tree: TypeTree, methods: Mapping[Label, Method], constraint: Expression) -> Set[object]
```

Default behavior:

- if a label is not present in `methods`, its method is `"all"`
- if the constraint is omitted in examples, it defaults to `BooleanConstant(True)`

There is only one constraint parameter because conjunction is already an AST constructor:

- `And(left, right)` combines constraints
- `BooleanConstant(True)` is the unconstrained case

Examples in this document MAY omit trailing default arguments. Therefore:

```python
generate(tree)
```

means:

```python
generate(tree, {}, BooleanConstant(True))
```

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

The canonical constraints on `Annotated[...]` are:

- it MAY contain at most one `ValueRange(...)`
- it MAY contain at most one `Name(...)`
- if it contains `ValueRange(min, max)`, then `base` MUST be `int`
- plain `int` MUST NOT appear unless it is immediately annotated with exactly one `ValueRange(...)`
- `label` MUST be a non-empty string

The value space is finite by construction.

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

## Validation Rules

A compliant implementation MUST reject invalid trees, including at least:

- `ValueRange(min, max)` with `min > max`
- `Name("")`
- plain `int` without a `ValueRange(...)`
- `Annotated[...]` with more than one `ValueRange(...)`
- `Annotated[...]` with more than one `Name(...)`
- `methods` containing a label that does not appear in the tree
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
- `label` is a `Label`
- `path` is a finite tuple of zero-based tuple indices

Examples:

```python
Reference("X", ())
Reference("X", (0,))
Reference("X", (1, 0))
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

- first take the assigned runtime value of `label`
- then follow the tuple indices in `path`

Address evaluation MUST fail if any step:

- indexes a non-tuple value, or
- uses an out-of-range index

### Mentioned labels

Define `mentioned_labels(expr)` recursively as the set of labels occurring in `Reference(label, path)` nodes.

This notion is used later for solver relevance and cacheability.

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
generate(tree, {}, BooleanConstant(True)) == values(tree)
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
generate(tree, methods, constraint) == {}
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

Otherwise, let `S := S0` and process every super label in ascending lexicographic order of the label string.

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
- the selection MAY depend on the full current assignment set `S`, not only on the projection

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

### Method `"arbitrarish_randomish"`

For label `L`, choose one value `v` from `projection(L, S)` using a non-deterministic heuristic policy, then replace `S` by:

```text
{ σ in S | σ(L) = v }
```

This method:

- MUST be non-deterministic
- MUST choose only values that are in `projection(L, S)`
- MUST satisfy the same non-emptiness invariant as the other witness methods
- SHOULD give non-zero probability to at least two different projected values whenever `projection(L, S)` has more than one member

This method prioritizes speed over distribution quality, while still aiming not to return the same witness all the time.

## Definition of `generate`

Let `S*` be the assignment set that remains after processing every super label according to its method.

Then:

```text
generate(tree, methods, constraint)
  = union(concretize(tree, σ) for every σ in S*)
```

This definition implies the key invariant:

- a super method MUST return a non-empty result if and only if the corresponding all-exhaustive problem is non-empty

Methods may change completeness, determinism, and distribution, but they MUST NOT introduce emptiness when satisfying assignments already exist.

## Solvers

### Solver suggestion

A compliant implementation SHOULD consider SAT-style, SMT-style, or CP-style solving techniques when computing:

- satisfiability of `Sat(tree, constraint)`
- exact conditional projections for `"uniform_random"`
- deterministic witness selection for difficult `"arbitrary"` cases

The spec does not require any particular backend.

### Solver locality

A solver is not required merely because a value is super.

If a label or subtree is unconstrained in the sense defined below, a compliant implementation MAY handle it by direct local enumeration or direct local witness selection.

In particular, if a super label:

- is not mentioned in `constraint`, and
- does not require cross-subtree domain intersection beyond its own closed region,

then a global solver is not required for that label.

## Caching

### Purpose of caching

Generation is extensional: the same subtree under the same relevant context denotes the same value set.

Caching is therefore semantically natural, not just an optimization trick.

A compliant implementation MUST have a well-defined caching model.

### Label-closed subtrees

For a subtree `u` inside a larger tree `t`, define `labels(u)` as the labels occurring in `u`.

`u` is label-closed in `t` if every occurrence in `t` of every label in `labels(u)` also lies inside `u`.

Intuition:

- a label-closed subtree contains the whole meaning of its own labels
- no outside occurrence can further narrow those labels by repeated-label intersection

### Constraint-independent subtrees

A subtree `u` is constraint-independent with respect to `constraint` if:

```text
labels(u) ∩ mentioned_labels(constraint) = ∅
```

Intuition:

- the constraint does not talk about any label inside `u`
- therefore `u` does not interact logically with the rest of the tree through the constraint

### Guaranteed-cacheable subtrees

A subtree is guaranteed-cacheable if it is both:

- label-closed, and
- constraint-independent

For every guaranteed-cacheable subtree `u`, the denotation of `u` depends only on:

- the subtree structure itself, and
- the methods restricted to `labels(u)`

It does not depend on the rest of the enclosing tree.

Therefore a compliant implementation MUST be able to memoize and reuse the generated values of `u` across distinct enclosing results without changing observable behavior.

At minimum, the semantic cache key for a guaranteed-cacheable subtree MUST be a function of:

- the subtree itself, and
- the methods restricted to the labels of that subtree

Implementations MAY cache broader classes of subtrees if they can prove semantic equivalence.

Caching compliance MAY be validated by instrumentation, tracing, or other implementation evidence. The observable outputs must remain exactly unchanged whether the cache is cold or warm.

### Immediate corollaries

The following are always guaranteed-cacheable:

- unnamed subtrees
- named subtrees whose labels are local to that subtree and not mentioned in the constraint

This includes the simple case requested by the core design:

- values that do not contain anything mentioned in the constraint can be cached, provided their labels are not shared outside the subtree

## Examples

The `"all"` examples below are exact.

The examples using `"arbitrary"`, `"uniform_random"`, or `"arbitrarish_randomish"` show one compliant outcome unless stated otherwise.

```python
generate(Literal[True], {}, BooleanConstant(True))
== { True }

generate(Tuple[bool, Literal["N\\A"]], {}, BooleanConstant(True))
== { (True, "N\\A"), (False, "N\\A") }

generate(Annotated[bool, Name("X")], {"X": "all"}, BooleanConstant(True))
== { True, False }

generate(Annotated[bool, Name("X")], {"X": "arbitrary"}, BooleanConstant(True))
== { True }

generate(Annotated[Tuple[bool, bool], Name("X")], {"X": "arbitrary"}, BooleanConstant(True))
== { (True, False) }

generate(
    Tuple[Annotated[bool, Name("X")], Annotated[bool, Name("Y")]],
    {"X": "all", "Y": "all"},
    Eq(Reference("X", ()), Reference("Y", ())),
)
== { (True, True), (False, False) }

generate(
    Tuple[Annotated[bool, Name("X")], Annotated[bool, Name("Y")]],
    {"X": "all", "Y": "all"},
    Ne(Reference("X", ()), Reference("Y", ())),
)
== { (True, False), (False, True) }

generate(
    Tuple[Annotated[bool, Name("X")], Annotated[bool, Name("Y")]],
    {"X": "all", "Y": "arbitrary"},
    Eq(Reference("X", ()), Reference("Y", ())),
)
== { (True, True) }

generate(
    Tuple[Annotated[bool, Name("X")], Annotated[bool, Name("Y")]],
    {"X": "all", "Y": "arbitrary"},
    Ne(Reference("X", ()), Reference("Y", ())),
)
== { (True, False) }

generate(
    Tuple[Annotated[bool, Name("X")], Annotated[bool, Name("Y")]],
    {"X": "arbitrary", "Y": "arbitrary"},
    Ne(Reference("X", ()), Reference("Y", ())),
)
== { (True, False) }

generate(
    Annotated[Tuple[bool, bool], Name("X")],
    {"X": "all"},
    Ne(Reference("X", (0,)), Reference("X", (1,))),
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
- implements the guaranteed-cacheable-subtree rule correctly
- returns plain runtime values as a set

For randomized methods, compliance has two layers:

- MUST-level shape guarantees
- SHOULD-level distribution-quality guarantees

### Compliance matrix

| ID | Level | Requirement | Input / Operation | Expected result |
| --- | --- | --- | --- | --- |
| GEN-01 | MUST | Literal generation | `generate(Literal[True], {}, BooleanConstant(True))` | `{True}` |
| GEN-02 | MUST | Unnamed tuple expansion | `generate(Tuple[bool, Literal["N\\A"]], {}, BooleanConstant(True))` | `{(True, "N\\A"), (False, "N\\A")}` |
| GEN-03 | MUST | Bounded integer expansion | `generate(Annotated[int, ValueRange(3, 4)], {}, BooleanConstant(True))` | `{3, 4}` |
| GEN-04 | MUST | Default method is `"all"` | `generate(Annotated[bool, Name("X")], {}, BooleanConstant(True))` | `{True, False}` |
| GEN-05 | MUST | Same label means same value | `generate(Tuple[Annotated[bool, Name("X")], Annotated[bool, Name("X")]], {"X": "all"}, BooleanConstant(True))` | `{(True, True), (False, False)}` |
| GEN-06 | MUST | Equality constraint with exhaustive methods | `generate(Tuple[Annotated[bool, Name("X")], Annotated[bool, Name("Y")]], {"X": "all", "Y": "all"}, Eq(Reference("X", ()), Reference("Y", ())))` | `{(True, True), (False, False)}` |
| GEN-07 | MUST | Inequality constraint with exhaustive methods | `generate(Tuple[Annotated[bool, Name("X")], Annotated[bool, Name("Y")]], {"X": "all", "Y": "all"}, Ne(Reference("X", ()), Reference("Y", ())))` | `{(True, False), (False, True)}` |
| GEN-08 | MUST | Address constraints work | `generate(Annotated[Tuple[bool, bool], Name("X")], {"X": "all"}, Ne(Reference("X", (0,)), Reference("X", (1,))))` | `{(True, False), (False, True)}` |
| GEN-09 | MUST | Repeated label domains intersect | `generate(Tuple[Annotated[int, ValueRange(1, 5), Name("X")], Annotated[int, ValueRange(3, 7), Name("X")]], {"X": "all"}, BooleanConstant(True))` | `{(3, 3), (4, 4), (5, 5)}` |
| GEN-10 | MUST | Impossible constraints produce empty output | `generate(Tuple[Annotated[bool, Name("X")], Annotated[bool, Name("Y")]], {"X": "all", "Y": "all"}, And(Eq(Reference("X", ()), Reference("Y", ())), Ne(Reference("X", ()), Reference("Y", ()))))` | `{}` |
| GEN-11 | MUST | `arbitrary` is a singleton subset of the `"all"` result when satisfiable | compare `generate(tree, {"X": "arbitrary"}, constraint)` against `generate(tree, {"X": "all"}, constraint)` | result cardinality is `1`, result is a subset of the `"all"` result |
| GEN-12 | MUST | `arbitrary` is deterministic | run the same `generate(...)` call with `"arbitrary"` repeatedly | same result every time |
| GEN-13 | MUST | Super methods preserve non-emptiness | for any satisfiable input, replace some `"all"` methods with super methods | output stays non-empty |
| GEN-14 | MUST | `uniform_random` returns a singleton subset of the `"all"` result when satisfiable | compare `generate(tree, {"X": "uniform_random"}, constraint)` against `generate(tree, {"X": "all"}, constraint)` | result cardinality is `1`, result is a subset of the `"all"` result |
| GEN-15 | SHOULD | `uniform_random` is statistically close to uniform when all labels are super and use `"uniform_random"` | sample many runs on a problem with several satisfying assignments | frequencies are close to uniform over satisfying outputs |
| GEN-16 | MUST | `arbitrarish_randomish` returns a singleton subset of the `"all"` result when satisfiable | compare `generate(tree, {"X": "arbitrarish_randomish"}, constraint)` against `generate(tree, {"X": "all"}, constraint)` | result cardinality is `1`, result is a subset of the `"all"` result |
| GEN-17 | SHOULD | `arbitrarish_randomish` shows some variation when several witnesses exist | sample many runs on a problem with several satisfying assignments | at least two distinct outputs appear |
| GEN-18 | MUST | Empty label is invalid | any tree containing `Name("")` | validation error |
| GEN-19 | MUST | Missing label reference in the expression is invalid | `generate(Annotated[bool, Name("X")], {}, Eq(Reference("Y", ()), BooleanConstant(True)))` | validation error |
| GEN-20 | MUST | Plain `int` is invalid in core | any tree containing plain `int` without `ValueRange(...)` | validation error |
| GEN-21 | MUST | `Expression` is AST-based, not source-text-based | pass a source string instead of an AST | type or validation error |
| GEN-22 | MUST | Single-constraint conjunction replaces a constraint set | compare `generate(tree, methods, And(c1, c2))` with the conceptual two-constraint case | same result as requiring both `c1` and `c2` |
| GEN-23 | MUST | Guaranteed-cacheable unnamed subtrees are cacheable | any unnamed subtree reused in many outputs | implementation can demonstrate semantic reuse without changing output |
| GEN-24 | MUST | Guaranteed-cacheable closed unconstrained named subtrees are cacheable | subtree is label-closed and its labels are disjoint from `mentioned_labels(constraint)` | implementation can demonstrate semantic reuse across enclosing outputs without changing output |

## Summary

This core has one observable interface:

```python
generate(tree, methods, constraint)
```

Its semantics are governed by five ideas:

- unnamed structure expands exhaustively
- `Name(label)` defines variable identity
- `Expression` restricts admissible assignments
- super methods collapse selected labels to one witness
- guaranteed-cacheable regions can be reused safely

The key invariant is the one that motivated this redesign:

- methods may change completeness, determinism, and distribution
- but they MUST NOT make a satisfiable problem empty

That property is part of compliance.
