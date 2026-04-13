# Spec 1: Core Generate Semantics

## Purpose

This document specifies the core semantics of the library as a single generation interface over finite type trees, label assignments, and boolean constraints.

The core is defined by observable behavior only.

It does not require any specific internal architecture. A compliant implementation MAY use staged expansion, direct search, a solver-backed model, or some other implementation strategy.

## Scope

The core MUST support:

- finite boolean domains
- finite bounded integer domains via `ValueRange`
- literal values
- tuples
- unions
- named subtrees via `Name(label)`
- parsed boolean constraint expressions over labels and addresses
- one public generation function

The core does not specify:

- compilation from any other representation
- dataclass-specific behavior
- a particular parser implementation strategy
- a particular solver backend

## Normative Terms

The words MUST, MUST NOT, SHOULD, SHOULD NOT, and MAY are to be interpreted as normative requirements.

## Core Interface

```python
Label: TypeAlias = str
Method: TypeAlias = Literal["all", "arbitrary", "uniform_random", "arbitrarish_randomish"]
Constraint: TypeAlias = Expr

generate(tree: TypeTree, methods: Mapping[Label, Method], constraints: Set[Constraint]) -> Set[object]
```

Default behavior:

- if a label is not present in `methods`, its method is `"all"`
- if `constraints` is empty, it is equivalent to `{ "True" }`

Examples in this document MAY omit trailing default arguments. Therefore:

```python
generate(tree)
```

means:

```python
generate(tree, {}, {})
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

### Structural equality and sets

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
- constraints referring to a label that does not appear in the tree

The implementation MAY reject additional malformed inputs if they are outside this spec.

## Constraint Language

### Constraint type

`Constraint` is an expression in the grammar below.

Implementations MAY store parsed ASTs internally, but they MUST accept expressions written in the textual syntax defined here.

The set of constraints is conjunctive:

- every constraint in the set MUST evaluate to `True`
- an empty set is equivalent to `{ "True" }`

### Grammar

```text
Expr      := OrExpr
OrExpr    := AndExpr ("or" AndExpr)*
AndExpr   := CmpExpr ("and" CmpExpr)*
CmpExpr   := SumExpr (("==" | "!=" | "<" | "<=" | ">" | ">=") SumExpr)?
SumExpr   := ProdExpr (("+" | "-") ProdExpr)*
ProdExpr  := UnaryExpr (("*" | "//" | "%") UnaryExpr)*
UnaryExpr := Primary | "-" UnaryExpr
Primary   := "True" | "False" | IntLiteral | Ref | "(" Expr ")"
Ref       := Label Address*
Address   := "[" Nat "]"
```

### Labels and addresses

- `Label` syntax is implementation-defined, but it MUST at least support identifiers such as `X`, `Y`, and `score_1`
- an address is a zero-based tuple path, such as `X[0]` or `X[1][0]`
- address evaluation MUST fail if any step attempts to index a non-tuple value or an out-of-range position

### Type rules

- arithmetic operators apply only to integers
- ordered comparisons `<`, `<=`, `>`, `>=` apply only to integers
- equality and inequality apply by structural equality to booleans, integers, `None`, strings, and tuples thereof
- `and` and `or` apply only to booleans

### Examples

Valid expressions include:

```text
X > 5
X < Y and X > 0
(X < Y and X > 0) or X < 0
X[0] != X[1]
```

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
generate(tree, {}, {}) == values(tree)
```

## Effective Label Domains

For each named occurrence of label `L`, remove only the `Name(L)` metadata and call the resulting name-free subtree the occurrence domain tree.

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

Let `Labels(tree)` be the set of labels used in the tree.

A candidate assignment `σ` maps every label in `Labels(tree)` to one concrete runtime value.

An assignment is admissible if:

- for every label `L`, `σ(L)` is in `domain(L)`
- every constraint evaluates to `True` under `σ`

Let:

```text
Sat(tree, constraints)
```

denote the set of all admissible assignments.

If `Sat(tree, constraints)` is empty, then:

```text
generate(tree, methods, constraints) == {}
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

This is why:

```python
generate(Tuple[bool, Literal["N\\A"]], {}, {})
```

returns two tuples, while:

```python
generate(Annotated[Tuple[bool, bool], Name("X")], {"X": "all"}, {})
```

returns the values of one named tuple variable.

## Method Semantics

### Overview

Methods control how labels are fixed before concretization.

- `"all"` means do not pre-fix that label
- every other method chooses exactly one witness value for that label

Unnamed structure is never affected by methods. It always expands fully.

### Processing order

Let:

```text
S0 = Sat(tree, constraints)
```

If `S0` is empty, the result is `{}`.

Otherwise, let `S := S0` and process every label whose method is not `"all"` in ascending lexicographic order of the label string.

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

If every label uses `"uniform_random"`, then the final singleton assignment MUST be uniformly distributed over the satisfying assignments in `S0`, modulo deduplication of equal runtime outputs.

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

This method prioritizes speed over distribution quality, while still aiming to avoid returning the same witness all the time.

## Definition of `generate`

Let `S*` be the assignment set that remains after processing every non-`"all"` label according to its method.

Then:

```text
generate(tree, methods, constraints)
  = union(concretize(tree, σ) for every σ in S*)
```

This definition implies the key guarantee requested by the core design:

- a non-`"all"` method MUST return a non-empty result if and only if the corresponding `"all"` problem is non-empty

Methods may change completeness, determinism, and distribution, but they MUST NOT introduce emptiness when satisfying assignments already exist.

## Examples

The `"all"` examples below are exact.

The examples using `"arbitrary"`, `"uniform_random"`, or `"arbitrarish_randomish"` show one compliant outcome unless stated otherwise.

```python
generate(Literal[True], {}, {})
== { True }

generate(Tuple[bool, Literal["N\\A"]], {}, {})
== { (True, "N\\A"), (False, "N\\A") }

generate(Annotated[bool, Name("X")], {"X": "all"}, {})
== { True, False }

generate(Annotated[bool, Name("X")], {"X": "arbitrary"}, {})
== { True }

generate(Annotated[Tuple[bool, bool], Name("X")], {"X": "arbitrary"}, {})
== { (True, False) }

generate(
    Tuple[Annotated[bool, Name("X")], Annotated[bool, Name("Y")]],
    {"X": "all", "Y": "all"},
    {"X == Y"},
)
== { (True, True), (False, False) }

generate(
    Tuple[Annotated[bool, Name("X")], Annotated[bool, Name("Y")]],
    {"X": "all", "Y": "all"},
    {"X != Y"},
)
== { (True, False), (False, True) }

generate(
    Tuple[Annotated[bool, Name("X")], Annotated[bool, Name("Y")]],
    {"X": "all", "Y": "arbitrary"},
    {"X == Y"},
)
== { (True, True) }

generate(
    Tuple[Annotated[bool, Name("X")], Annotated[bool, Name("Y")]],
    {"X": "all", "Y": "arbitrary"},
    {"X != Y"},
)
== { (True, False) }

generate(
    Tuple[Annotated[bool, Name("X")], Annotated[bool, Name("Y")]],
    {"X": "arbitrary", "Y": "arbitrary"},
    {"X != Y"},
)
== { (True, False) }
```

The examples above are consistent with the required non-emptiness rule:

- if the `"all"` version has a non-empty satisfying set, then every witness-based method also has a non-empty result

## Compliance

A core implementation is compliant with this spec if it:

- accepts valid inputs covered by this document
- rejects invalid inputs covered by this document
- implements the denotation of unnamed trees correctly
- implements label-domain intersection correctly
- parses and evaluates constraints according to the grammar and type rules above
- implements method semantics and the non-emptiness invariant correctly
- returns plain runtime values as a set

For randomized methods, compliance has two layers:

- MUST-level shape guarantees
- SHOULD-level distribution-quality guarantees

### Compliance matrix

| ID | Level | Requirement | Input / Operation | Expected result |
| --- | --- | --- | --- | --- |
| GEN-01 | MUST | Literal generation | `generate(Literal[True], {}, {})` | `{True}` |
| GEN-02 | MUST | Unnamed tuple expansion | `generate(Tuple[bool, Literal["N\\A"]], {}, {})` | `{(True, "N\\A"), (False, "N\\A")}` |
| GEN-03 | MUST | Bounded integer expansion | `generate(Annotated[int, ValueRange(3, 4)], {}, {})` | `{3, 4}` |
| GEN-04 | MUST | Default method is `"all"` | `generate(Annotated[bool, Name("X")], {}, {})` | `{True, False}` |
| GEN-05 | MUST | Same label means same value | `generate(Tuple[Annotated[bool, Name("X")], Annotated[bool, Name("X")]], {"X": "all"}, {})` | `{(True, True), (False, False)}` |
| GEN-06 | MUST | Equality constraint with exhaustive methods | `generate(Tuple[Annotated[bool, Name("X")], Annotated[bool, Name("Y")]], {"X": "all", "Y": "all"}, {"X == Y"})` | `{(True, True), (False, False)}` |
| GEN-07 | MUST | Inequality constraint with exhaustive methods | `generate(Tuple[Annotated[bool, Name("X")], Annotated[bool, Name("Y")]], {"X": "all", "Y": "all"}, {"X != Y"})` | `{(True, False), (False, True)}` |
| GEN-08 | MUST | Address constraints work | `generate(Annotated[Tuple[bool, bool], Name("X")], {"X": "all"}, {"X[0] != X[1]"})` | `{(True, False), (False, True)}` |
| GEN-09 | MUST | Repeated label domains intersect | `generate(Tuple[Annotated[int, ValueRange(1, 5), Name("X")], Annotated[int, ValueRange(3, 7), Name("X")]], {"X": "all"}, {})` | `{(3, 3), (4, 4), (5, 5)}` |
| GEN-10 | MUST | Impossible constraints produce empty output | `generate(Tuple[Annotated[bool, Name("X")], Annotated[bool, Name("Y")]], {"X": "all", "Y": "all"}, {"X == Y", "X != Y"})` | `{}` |
| GEN-11 | MUST | `arbitrary` is a singleton subset of the `"all"` result when satisfiable | compare `generate(tree, {"X": "arbitrary"}, constraints)` against `generate(tree, {"X": "all"}, constraints)` | result cardinality is `1`, result is a subset of the `"all"` result |
| GEN-12 | MUST | `arbitrary` is deterministic | run the same `generate(...)` call with `"arbitrary"` repeatedly | same result every time |
| GEN-13 | MUST | Witness methods preserve non-emptiness | for any satisfiable input, replace some `"all"` methods with witness methods | output stays non-empty |
| GEN-14 | MUST | `uniform_random` returns a singleton subset of the `"all"` result when satisfiable | compare `generate(tree, {"X": "uniform_random"}, constraints)` against `generate(tree, {"X": "all"}, constraints)` | result cardinality is `1`, result is a subset of the `"all"` result |
| GEN-15 | SHOULD | `uniform_random` is statistically close to uniform when all labels use `"uniform_random"` | sample many runs on a problem with several satisfying assignments | frequencies are close to uniform over satisfying outputs |
| GEN-16 | MUST | `arbitrarish_randomish` returns a singleton subset of the `"all"` result when satisfiable | compare `generate(tree, {"X": "arbitrarish_randomish"}, constraints)` against `generate(tree, {"X": "all"}, constraints)` | result cardinality is `1`, result is a subset of the `"all"` result |
| GEN-17 | SHOULD | `arbitrarish_randomish` shows some variation when several witnesses exist | sample many runs on a problem with several satisfying assignments | at least two distinct outputs appear |
| GEN-18 | MUST | Empty label is invalid | any tree containing `Name("")` | validation error |
| GEN-19 | MUST | Missing label reference in constraints is invalid | `generate(Annotated[bool, Name("X")], {}, {"Y == True"})` | validation error |
| GEN-20 | MUST | Plain `int` is invalid in core | any tree containing plain `int` without `ValueRange(...)` | validation error |

## Summary

This core has one observable interface:

```python
generate(tree, methods, constraints)
```

Its semantics are governed by four ideas:

- unnamed structure expands exhaustively
- `Name(label)` defines variable identity
- constraints restrict admissible label assignments
- methods decide which labels stay exhaustive and which are fixed to one witness

The key invariant is the one that motivated this redesign:

- methods may change completeness, determinism, and distribution
- but they MUST NOT make a satisfiable problem empty

That property is part of compliance.
