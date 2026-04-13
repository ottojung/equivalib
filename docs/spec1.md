# Spec 1: Core TypeTree Semantics

## Purpose

This document specifies the "core" layer of the library.

The core is intentionally smaller than the current repository surface. It is the layer that operates on finite type trees, finite domains, and labelled symbolic leaves. It does not know about Python dataclasses, `__post_init__`, OR-Tools, or sentence construction.

The purpose of this split is architectural: the current repository mixes structural expansion with symbolic identity management. The core defined here makes symbolic identity explicit.

The key rule is:

- symbolic identity is defined by `Super(label)`
- not by occurrence position
- and not by structural equality alone

If two symbolic occurrences are intended to be independent, they MUST have different labels. If they are intended to denote the same logical variable, they MUST reuse the same label.

## Scope

The core MUST support:

- finite boolean domains
- finite integer ranges
- literal values
- tuples
- unions
- labelled symbolic leaves via `Super(label)`
- two conceptual stages:
  - `generate_ground(tree)`
  - `collapse(tree, label, method)`

The core does not specify:

- dataclass compilation
- solver-based relational constraints
- runtime Python object instantiation
- a particular internal class hierarchy

Those can live in higher layers that compile down to and interpret this core.

## Layer Boundary

The intended layering is:

1. A frontend maps user-facing Python types and constraints into core `TypeTree` values plus labels.
2. The core performs structural expansion and label-based refinement.
3. A higher layer may project refined trees back into runtime objects.

This means a frontend has an important responsibility:

- if two symbolic field occurrences are independent, it MUST allocate different labels
- if two symbolic field occurrences are intentionally linked, it MUST reuse the same label

That rule is the architectural fix for the aliasing problem observed in the current repository.

## Normative Terms

The words MUST, MUST NOT, SHOULD, SHOULD NOT, and MAY are to be interpreted as normative requirements.

## Core Concepts

### Canonical constructors

The core is specified in terms of these conceptual constructors:

```text
TypeTree :=
    bool
  | None
  | Literal[value]
  | IntRange(min, max)
  | Tuple[t1, t2, ..., tn]
  | Union[t1, t2, ..., tn]
  | Annotated[domain, Super(label)]
```

Where:

- `value` is a literal boolean, integer, or string in core v1
- `IntRange(min, max)` denotes the finite closed interval `{min, min+1, ..., max}`
- `label` is a non-empty string
- `domain` in an input `Annotated[..., Super(label)]` MUST be one of:
  - `bool`
  - `IntRange(min, max)`

### Surface syntax sugar

The implementation MAY accept frontend sugar, but the following normalizations MUST hold semantically:

```text
Annotated[int, ValueRange(a, b)]
    == IntRange(a, b)

Annotated[int, ValueRange(a, b), Super(label)]
    == Annotated[IntRange(a, b), Super(label)]
```

So the spec uses `IntRange(...)` as the canonical range constructor, while allowing `Annotated[int, ValueRange(...)]` as frontend syntax.

### GroundTypeTree

A `GroundTypeTree` is a `TypeTree` with these properties:

- it contains no plain `bool`
- it contains no plain `IntRange(...)`
- it contains no `Union[...]`
- it may still contain symbolic leaves of the form:
  - `Annotated[bool, Super(label)]`
  - `Annotated[IntRange(min, max), Super(label)]`
  - `Annotated[Literal[value], Super(label)]`
- tuples are allowed recursively
- `None` is allowed
- `Literal[value]` is allowed

Intuitively, a ground tree has had all non-symbolic branching expanded, but symbolic leaves may remain abstract.

### TypeTreeInstance

A `TypeTreeInstance` is the result of zero or more `collapse(...)` operations applied to a ground tree.

In this spec, a collapsed symbolic occurrence keeps its label provenance and becomes:

```text
Annotated[Literal[value], Super(label)]
```

This preserves the information that a concrete choice came from a symbolic label.

Implementations MAY also provide a projection that drops the annotation and produces plain runtime values, but that projection is outside this spec.

### Structural equality and sets

All result collections in this spec are mathematical sets.

Therefore:

- duplicates MUST be removed by structural equality
- result ordering is not observable
- union branch order is not semantically observable
- tuple element order remains semantically significant

## Label Semantics

`Super(label)` is not decorative metadata. It defines variable identity.

The core MUST satisfy all of the following:

- two occurrences with the same label denote the same logical symbolic variable
- two occurrences with different labels denote different logical symbolic variables, even if their wrapped domains are structurally equal
- `generate_ground(...)` MUST preserve labels unchanged
- `collapse(tree, label, ...)` MUST affect only occurrences whose label exactly matches `label`
- an implementation MUST NOT merge two different labels merely because their wrapped domains are equal

### Compatible repeated labels

A label MAY occur more than once in the same tree.

When it does, all occurrences of that label MUST have the same base sort:

- boolean sort
- integer sort

Within a sort, repeated occurrences MAY narrow each other. For example:

```text
Annotated[IntRange(1, 5), Super("X")]
Annotated[IntRange(3, 7), Super("X")]
```

are compatible and jointly imply the effective domain `{3, 4, 5}`.

### Invalid repeated labels

If the same label appears with incompatible base sorts, the tree is invalid.

Example:

```text
Tuple[
  Annotated[bool, Super("X")],
  Annotated[IntRange(1, 3), Super("X")]
]
```

This MUST be rejected as invalid input by the implementation, either during validation or at the first operation that requires validation.

## Stage 1: `generate_ground`

### Signature

```text
generate_ground(tree: TypeTree) -> Set[GroundTypeTree]
```

### Intent

`generate_ground(...)` expands all non-symbolic branching and leaves symbolic leaves intact.

It does not solve labels and it does not choose symbolic values.

### Recursive semantics

The semantics of `generate_ground(...)` are:

```text
generate_ground(None)
  = { None }

generate_ground(Literal[v])
  = { Literal[v] }

generate_ground(bool)
  = { Literal[True], Literal[False] }

generate_ground(IntRange(min, max))
  = { Literal[min], Literal[min+1], ..., Literal[max] }

generate_ground(Union[t1, t2, ..., tn])
  = generate_ground(t1)
    union generate_ground(t2)
    union ...
    union generate_ground(tn)

generate_ground(Tuple[t1, t2, ..., tn])
  = {
      Tuple[g1, g2, ..., gn]
      | g1 in generate_ground(t1),
        g2 in generate_ground(t2),
        ...,
        gn in generate_ground(tn)
    }

generate_ground(Annotated[domain, Super(label)])
  = { Annotated[domain, Super(label)] }
```

### Validation rules

The implementation MUST reject invalid input trees, including at least:

- `IntRange(min, max)` where `min > max`
- `Super(label)` where `label` is empty
- symbolic wrappers around unsupported input domains

### Examples

```text
generate_ground(bool)
  == { Literal[True], Literal[False] }

generate_ground(Tuple[bool, Literal["N\\A"]])
  == {
       Tuple[Literal[True],  Literal["N\\A"]],
       Tuple[Literal[False], Literal["N\\A"]]
     }

generate_ground(IntRange(-5, 7))
  == {
       Literal[-5], Literal[-4], Literal[-3], Literal[-2], Literal[-1],
       Literal[0], Literal[1], Literal[2], Literal[3], Literal[4],
       Literal[5], Literal[6], Literal[7]
     }

generate_ground(Annotated[bool, Super("X")])
  == { Annotated[bool, Super("X")] }

generate_ground(Tuple[bool, Union[Annotated[bool, Super("X")], None]])
  == {
       Tuple[Literal[True],  None],
       Tuple[Literal[False], None],
       Tuple[Literal[True],  Annotated[bool, Super("X")]],
       Tuple[Literal[False], Annotated[bool, Super("X")]]
     }

generate_ground(Tuple[Union[Annotated[bool, Super("X")], None], IntRange(3, 4)])
  == {
       Tuple[None,                          Literal[3]],
       Tuple[None,                          Literal[4]],
       Tuple[Annotated[bool, Super("X")],  Literal[3]],
       Tuple[Annotated[bool, Super("X")],  Literal[4]]
     }
```

## Stage 2: `collapse`

### Signature

```text
collapse(
    tree: GroundTypeTree,
    label: str,
    method: Literal["all", "arbitrary", "uniform_random", "arbitrarish_randomish"]
) -> Set[TypeTreeInstance]
```

### Intent

`collapse(...)` refines all occurrences of one symbolic label within one ground tree.

The refinement is simultaneous across every occurrence of the target label.

### Effective domain

For a given `tree` and target `label`, define the set of target occurrences as every subtree of one of these forms:

- `Annotated[bool, Super(label)]`
- `Annotated[IntRange(min, max), Super(label)]`
- `Annotated[Literal[value], Super(label)]`

Each target occurrence contributes a finite value set:

```text
values(Annotated[bool, Super(label)])
  = { True, False }

values(Annotated[IntRange(min, max), Super(label)])
  = { min, min+1, ..., max }

values(Annotated[Literal[v], Super(label)])
  = { v }
```

If there are no target occurrences, then for all methods:

```text
collapse(tree, label, method) == { tree }
```

If there are target occurrences, their effective domain is the intersection of their contributed value sets.

```text
effective_domain(tree, label)
  = intersection(values(occurrence_i) for each target occurrence i)
```

If the intersection is empty, then:

```text
collapse(tree, label, "all") == {}
```

and every other method MUST also return `{}`.

### Refinement

For each `v` in the effective domain, define `refine(tree, label, v)` as the tree obtained by replacing every target occurrence with:

```text
Annotated[Literal[v], Super(label)]
```

All non-target subtrees MUST remain unchanged.

### Semantics by method

Let:

```text
ALL(tree, label) = { refine(tree, label, v) | v in effective_domain(tree, label) }
```

Then the methods are defined as follows.

#### Method `"all"`

```text
collapse(tree, label, "all") == ALL(tree, label)
```

This method MUST return the full set of refinements.

#### Method `"arbitrary"`

If `ALL(tree, label)` is empty, return `{}`.

Otherwise return any singleton subset of `ALL(tree, label)`.

No fairness or determinism guarantee is required.

#### Method `"uniform_random"`

If `ALL(tree, label)` is empty, return `{}`.

Otherwise return a singleton subset of `ALL(tree, label)` selected uniformly over the distinct members of `ALL(tree, label)`.

#### Method `"arbitrarish_randomish"`

If `ALL(tree, label)` is empty, return `{}`.

Otherwise return a singleton subset of `ALL(tree, label)`.

This method is explicitly heuristic. It MAY be biased and does not need to be uniform.

### Important semantic consequences

#### Same label means same value

```text
collapse(
  Tuple[
    Annotated[bool, Super("X")],
    Annotated[bool, Super("X")]
  ],
  "X",
  "all"
)
== {
     Tuple[
       Annotated[Literal[True],  Super("X")],
       Annotated[Literal[True],  Super("X")]
     ],
     Tuple[
       Annotated[Literal[False], Super("X")],
       Annotated[Literal[False], Super("X")]
     ]
   }
```

The core MUST NOT produce mixed `True/False` combinations for the same label.

#### Different labels are independent

```text
collapse(
  Tuple[
    Annotated[bool, Super("X")],
    Annotated[bool, Super("Y")]
  ],
  "X",
  "all"
)
== {
     Tuple[
       Annotated[Literal[True],  Super("X")],
       Annotated[bool,           Super("Y")]
     ],
     Tuple[
       Annotated[Literal[False], Super("X")],
       Annotated[bool,           Super("Y")]
     ]
   }
```

Only the target label changes.

#### Range intersection

```text
collapse(
  Tuple[
    Annotated[IntRange(1, 5), Super("X")],
    Annotated[IntRange(3, 7), Super("X")]
  ],
  "X",
  "all"
)
== {
     Tuple[
       Annotated[Literal[3], Super("X")],
       Annotated[Literal[3], Super("X")]
     ],
     Tuple[
       Annotated[Literal[4], Super("X")],
       Annotated[Literal[4], Super("X")]
     ],
     Tuple[
       Annotated[Literal[5], Super("X")],
       Annotated[Literal[5], Super("X")]
     ]
   }
```

#### Idempotence after collapse

If a label is already fully refined to one literal, then collapsing it again MUST return the same singleton tree.

Example:

```text
collapse(Annotated[Literal[True], Super("X")], "X", "all")
  == { Annotated[Literal[True], Super("X")] }
```

## Derived Usage Pattern

The core only collapses one label at a time. To refine multiple labels, a caller repeatedly applies `collapse(...)` across a set of current trees.

Conceptually:

```text
expand_label_set(trees, label, method)
  = union(collapse(tree, label, method) for tree in trees)
```

Then a full pipeline can look like:

```text
trees0 = generate_ground(tree)
trees1 = expand_label_set(trees0, "X", "all")
trees2 = expand_label_set(trees1, "Y", "all")
...
```

This staged API is intentional. It keeps symbolic identity explicit and local.

## Compliance

A core implementation is compliant with this spec if it:

- accepts all valid inputs covered by this document
- rejects invalid inputs covered by this document
- satisfies the exact set semantics of `generate_ground(...)`
- satisfies the exact label semantics of `collapse(..., "all")`
- satisfies the subset and cardinality properties of the non-`"all"` methods

For randomized methods, compliance has two parts:

- MUST-level shape guarantees
- SHOULD-level distribution guarantees

### Compliance matrix

| ID | Level | Requirement | Input / Operation | Expected result |
| --- | --- | --- | --- | --- |
| GG-01 | MUST | Boolean grounding | `generate_ground(bool)` | `{Literal[True], Literal[False]}` |
| GG-02 | MUST | Literal stability | `generate_ground(Literal[5])` | `{Literal[5]}` |
| GG-03 | MUST | Range grounding is finite and inclusive | `generate_ground(IntRange(-1, 1))` | `{Literal[-1], Literal[0], Literal[1]}` |
| GG-04 | MUST | Frontend range sugar normalizes correctly | `generate_ground(Annotated[int, ValueRange(3, 4)])` | `{Literal[3], Literal[4]}` |
| GG-05 | MUST | Tuple grounding is cartesian product | `generate_ground(Tuple[bool, Literal["N\\A"]])` | `{Tuple[Literal[True], Literal["N\\A"]], Tuple[Literal[False], Literal["N\\A"]]}` |
| GG-06 | MUST | Union grounding deduplicates equal branches | `generate_ground(Union[bool, bool])` | `{Literal[True], Literal[False]}` |
| GG-07 | MUST | `None` behaves as a singleton branch | `generate_ground(Union[bool, None])` | `{Literal[True], Literal[False], None}` |
| GG-08 | MUST | Symbolic leaves are preserved | `generate_ground(Annotated[bool, Super("X")])` | `{Annotated[bool, Super("X")]}` |
| GG-09 | MUST | Mixed ground generation preserves symbolic leaves while expanding concrete branches | `generate_ground(Tuple[bool, Union[Annotated[bool, Super("X")], None]])` | `{Tuple[Literal[True], None], Tuple[Literal[False], None], Tuple[Literal[True], Annotated[bool, Super("X")]], Tuple[Literal[False], Annotated[bool, Super("X")]]}` |
| CL-01 | MUST | Absent label is identity | `collapse(Literal[True], "X", "all")` | `{Literal[True]}` |
| CL-02 | MUST | `all` over a boolean symbol returns both refinements | `collapse(Annotated[bool, Super("X")], "X", "all")` | `{Annotated[Literal[True], Super("X")], Annotated[Literal[False], Super("X")]}` |
| CL-03 | MUST | `all` over a range symbol returns all refinements | `collapse(Annotated[IntRange(3, 4), Super("X")], "X", "all")` | `{Annotated[Literal[3], Super("X")], Annotated[Literal[4], Super("X")]}` |
| CL-04 | MUST | Same label collapses simultaneously across all occurrences | `collapse(Tuple[Annotated[bool, Super("X")], Annotated[bool, Super("X")]], "X", "all")` | exactly two results, both positions equal in each result |
| CL-05 | MUST | Same label with compatible ranges intersects domains | `collapse(Tuple[Annotated[IntRange(1, 5), Super("X")], Annotated[IntRange(3, 7), Super("X")]], "X", "all")` | exactly `{3, 4, 5}` projected through both positions |
| CL-06 | MUST | Same label with disjoint compatible ranges yields empty result | `collapse(Tuple[Annotated[IntRange(1, 2), Super("X")], Annotated[IntRange(5, 6), Super("X")]], "X", "all")` | `{}` |
| CL-07 | MUST | Same label with incompatible sorts is invalid | `collapse(Tuple[Annotated[bool, Super("X")], Annotated[IntRange(1, 3), Super("X")]], "X", "all")` | invalid-tree error |
| CL-08 | MUST | Non-target labels remain symbolic | `collapse(Tuple[Annotated[bool, Super("X")], Annotated[bool, Super("Y")]], "X", "all")` | two results where only `"X"` is refined |
| CL-09 | MUST | `arbitrary` returns either empty or a singleton subset of `all` | compare `collapse(tree, "X", "arbitrary")` against `collapse(tree, "X", "all")` | result cardinality is `0` or `1`, and every member is in `all` |
| CL-10 | MUST | `uniform_random` returns either empty or a singleton subset of `all` | compare `collapse(tree, "X", "uniform_random")` against `collapse(tree, "X", "all")` | result cardinality is `0` or `1`, and every member is in `all` |
| CL-11 | SHOULD | `uniform_random` is statistically close to uniform over repeated trials | sample `collapse(Annotated[bool, Super("X")], "X", "uniform_random")` many times | both boolean outcomes appear with near-equal frequency |
| CL-12 | MUST | `arbitrarish_randomish` returns either empty or a singleton subset of `all` | compare `collapse(tree, "X", "arbitrarish_randomish")` against `collapse(tree, "X", "all")` | result cardinality is `0` or `1`, and every member is in `all` |
| CL-13 | MUST | Re-collapsing an already refined label is idempotent | `collapse(Annotated[Literal[True], Super("X")], "X", "all")` | `{Annotated[Literal[True], Super("X")]}` |

## Summary of the Architectural Rule

The most important invariant in this spec is simple:

- structure controls branching
- labels control symbolic identity

`generate_ground(...)` expands structure.

`collapse(...)` refines one label at a time.

A compliant implementation MUST NOT infer symbolic aliasing from repeated structure alone. Symbolic aliasing exists only when the same `Super(label)` appears more than once.