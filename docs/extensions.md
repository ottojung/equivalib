# Extensions for equivalib Core

## Purpose

This document specifies a planned extension mechanism for `equivalib.core.generate`.

The base core described in [docs/spec1.md](spec1.md) handles a fixed leaf language: booleans, integers, literals, tuples, unions, and named occurrences. The extension mechanism adds a controlled way to introduce new leaf syntaxes and to override built-in leaves such as `bool`.

The goal is to extend the tree language without collapsing the design boundaries that the current core already enforces:

- tree normalization remains separate from constraint solving,
- constraint solving remains separate from witness selection,
- witness selection remains separate from concretization,
- extension behavior remains explicit and local rather than implicit and global.

This document is intentionally written against the current implementation shape in `src/equivalib/core`.

In particular, the current engine already has a concrete lifecycle:

1. accept `tree`, `constraint`, and `methods`,
2. normalize the tree,
3. validate the expression and methods,
4. infer integer bounds from constraints,
5. validate the filled tree,
6. search for satisfying assignments,
7. apply witness-selection methods,
8. concretize surviving assignments into runtime values.

The extension mechanism must fit that lifecycle rather than replace it.

## Scope

This extension spec covers:

- custom leaf syntaxes inside the tree,
- overriding built-in leaves such as `bool`,
- adding extra constraints during an initialization pass,
- extension-aware exhaustive generation,
- extension-aware arbitrary witness selection,
- extension-aware uniform-random witness selection,
- finite and infinite extension domains,
- the interaction between extensions and the current core method semantics.

This extension spec does not yet cover:

- extension-defined addressable tuple structure,
- extension-specific AST nodes,
- direct SAT/CP-SAT plugin APIs,
- extension support for `values(...)`,
- dataclass compilation onto extension-owned leaves.

Those are deliberately postponed so that the first extension design can stay compatible with the current core internals.

## Design Constraints from the Current Core

Studying the current implementation exposes four hard constraints that the extension API must respect.

### 1. `initialize` must run before validation and bounds inference

The current `generate(...)` pipeline validates expressions and infers integer bounds before search begins.

Therefore any extension hook that adds constraints must run before:

- expression validation,
- integer-bounds inference,
- tree validation,
- search.

Otherwise an extension could not tighten integer bounds or reject malformed cross-label constraints early enough.

### 2. Extension-owned leaves need per-occurrence context

The user-facing request says an extension provides:

- `enumerate_all`
- `uniform_random`
- `arbitrary`

with no arguments.

That is not precise enough for parameterized leaves such as a regex leaf carrying a pattern like `Regex("a*")` or two different regex leaves in the same tree.

Therefore the semantic model in this document treats those operations as acting on the currently matched extension-owned leaf occurrence.

An implementation MAY realize this in either of two ways:

- by passing the matched leaf explicitly to the hook, or
- by binding per-occurrence state during normalization or initialization and then calling an effectively zero-argument bound method.

The semantic requirement is per-occurrence behavior; the exact plumbing is an implementation detail.

### 3. Raw-domain witness hooks are not enough under constraints

The current core does not choose arbitrary or random values from raw domains.

It first computes satisfying assignments, then applies methods over the surviving per-label projections.

That means a naive hook like:

- `arbitrary() -> A`
- `uniform_random() -> A`

cannot by itself preserve the current core invariants once the extension-owned label participates in constraints.

For example, a raw arbitrary value might not lie in the satisfying projection at all.

Therefore this document refines the requested API so that extension witness hooks are defined relative to the current satisfying projection whenever the implementation has materialized it.

### 4. Expression typing is still a core concern

The current validator classifies expressions as:

- boolean,
- numeric,
- or opaque/`any`.

Without an additional contract, a custom leaf cannot safely participate in:

- address paths,
- arithmetic,
- ordering.

The first extension version therefore keeps custom leaves atomic by default.

Only two built-in override cases get richer typing in v1:

- an extension registered under `bool` remains boolean-typed,
- an extension registered under `int` remains numeric-typed.

All other extension-owned leaves are treated as atomic opaque values for expression typing.

## Public Surface

The extension-aware public entry point is:

```python
generate(
    tree: object,
    constraint: Expression = BooleanExpression(True),
    methods: Optional[Mapping[Label, Method]] = None,
    extensions: Optional[Mapping[type[object], Extension[object]]] = None,
) -> set[object]
```

As in the base core:

- `methods` defaults to `{}` semantically,
- missing labels default to method `"all"`,
- `constraint` defaults to `BooleanExpression(True)`.

For extensions:

- if `extensions` is `None`, generation uses only the built-in core leaf language,
- if `extensions` is provided, built-in and extension-owned leaves may appear in the same tree,
- unused extension registry entries are permitted.

### Registry keys

The registry key is the syntactic head that identifies which extension owns a leaf.

This is intentionally about tree syntax, not necessarily the runtime type of generated values.

Example:

- a registry key `Regex` may produce runtime `str` values,
- a registry key `bool` may still produce runtime `bool` values but with custom domain or witness behavior.

## Extension Interface

The requested API can be made precise as the following semantic protocol:

```python
class Extension(Protocol[A]):
    def initialize(self, tree: object, constraint: Expression) -> Expression | None:
        ...

    def enumerate_all(self, owner: object) -> Iterator[A]:
        ...

    def arbitrary(self, owner: object, values: Collection[A] | None = None) -> A:
        ...

    def uniform_random(
        self,
        owner: object,
        weighted_values: Sequence[tuple[A, int]] | None = None,
    ) -> A:
        ...
```

The semantic meaning is:

- `initialize(...)` is called once per registered extension at the start of `generate(...)`,
- `owner` is the matched extension-owned leaf occurrence,
- `enumerate_all(owner)` returns the exhaustive domain for that occurrence,
- `arbitrary(owner, values)` chooses one deterministic witness from the current satisfying projection when `values` is provided,
- `uniform_random(owner, weighted_values)` chooses one witness from the current satisfying projection with multiplicity-aware weights when `weighted_values` is provided.

The optional projection arguments are not cosmetic. They are required to preserve the current method semantics when extension-owned leaves participate in constraints.

Implementations MAY internally adapt this protocol to the simpler requested shape if they can bind `owner` and projection state safely, but the observable behavior must match this document.

## Matching Rules

Extension lookup is performed after peeling one `Annotated[...]` wrapper layer for `Name(...)` handling.

Let `base` be the leaf payload after removing the outermost `Annotated` wrapper, if present.

Matching then works as follows:

1. If `base` is a plain type object and `base in extensions`, that extension owns the leaf.
2. If `base` is not a plain type object and `type(base) in extensions`, that extension owns the leaf.
3. Otherwise the built-in core rules apply.

This permits both of the following styles:

- built-in override: `bool` matched by key `bool`,
- parameterized custom leaf: `Regex("ab|cd")` matched by key `Regex`.

Examples:

```python
bool
Annotated[bool, Name("B")]
Regex("ab|cd")
Annotated[Regex("a*"), Name("R")]
Tuple[Regex("ab|cd"), bool]
```

## Initialize Phase

Before normalization, `generate(...)` must call:

```python
extra_i = extension_i.initialize(tree, constraint)
```

for every registered extension.

Each extension receives:

- the original input tree,
- the original input constraint.

Each extension returns either:

- `None`, or
- one additional boolean `Expression`.

The effective constraint is then:

```text
constraint_eff = And(constraint, extra_1, extra_2, ..., extra_n)
```

where `None` returns are skipped.

Important consequences:

- initialize is a one-shot pre-pass,
- every extension sees the same original `(tree, constraint)` pair,
- initialize order must not affect observable behavior,
- extra constraints participate in all later validation and bounds inference,
- an initialize-returned constraint may make the whole problem unsatisfiable.

Returned constraints must satisfy the same rules as ordinary user constraints:

- they must be `Expression` ASTs,
- they must be boolean at the top level,
- they must reference only labels that occur in the tree,
- they must use only valid address paths.

## Internal Representation Plan

The current core normalizes trees into a small IR (`BoolNode`, `TupleNode`, `NamedNode`, and so on).

The cleanest implementation path is to add one new IR node:

```python
ExtensionNode(key: type[object], owner: object, kind: Literal["bool", "int", "opaque"])
```

where:

- `key` is the registry key,
- `owner` is the matched leaf payload,
- `kind` is the expression-typing category.

Planned kind rules for v1:

- key `bool` -> `kind="bool"`
- key `int` -> `kind="int"`
- every other extension key -> `kind="opaque"`

This choice keeps the validator aligned with the existing architecture without forcing a larger typed-extension API in the first iteration.

## Expression and Validation Semantics

### Default rule: extension-owned leaves are atomic

Unless the registry key is the built-in `bool` or `int`, an extension-owned leaf is atomic.

That means:

- `Reference(label, ())` is valid,
- `Reference(label, path)` with a non-empty path is invalid,
- `Eq` and `Ne` may compare such values structurally,
- `Lt`, `Le`, `Gt`, and `Ge` are invalid,
- `Add`, `Sub`, `Mul`, `FloorDiv`, `Mod`, and `Neg` are invalid,
- direct boolean use in `And`/`Or` is invalid.

This is not a claim about the runtime value's Python type. It is a claim about the expression language supported by v1 extensions.

### Built-in overrides

If an extension is registered under:

- `bool`, then references to that leaf remain boolean-typed in expressions,
- `int`, then references to that leaf remain numeric-typed in expressions.

This rule is required so that built-in overrides preserve the core expression language.

## Domain Semantics

### Unnamed extension-owned leaves

For an unnamed extension-owned leaf `u`, its denotation is:

```text
values_ext(u) = set(extension.enumerate_all(u))
```

if exhaustive generation is requested.

If `enumerate_all(u)` cannot produce a finite exhaustive iterator, it MUST raise an exception.

### Named extension-owned leaves

For a named occurrence `Annotated[u, Name("X")]`, the label domain is the extension-owned leaf's denotation.

Repeated-label occurrences still intersect exactly as they do in the base core:

```text
domain(X) = intersection(denotation_i for every occurrence i of label X)
```

with structural equality used for value comparison.

This preserves the current core meaning of repeated labels.

## Method Semantics for Extensions

The current core semantics must remain true:

- `"all"` preserves all satisfying variation,
- `"arbitrary"` chooses one witness from the current satisfying projection,
- `"uniform_random"` chooses one witness from the current satisfying projection weighted by supporting-assignment multiplicity.

Extensions therefore integrate at two distinct layers.

### 1. Exhaustive layer

`enumerate_all(owner)` defines the raw denotation for exhaustive exploration.

This is needed for:

- unnamed extension-owned leaves,
- named labels using `"all"`,
- any constrained case where the implementation must materialize the satisfying projection.

### 2. Witness-selection layer

When the core is selecting a witness for a super label, the extension may be asked to choose among already-admissible values.

For `"arbitrary"`:

- if the implementation has materialized the satisfying projection for the label, it MUST call `arbitrary(owner, values)` with that projection,
- if the implementation has not materialized a finite projection but can still request a direct witness from the extension, it MAY call `arbitrary(owner, None)`.

For `"uniform_random"`:

- if the implementation has materialized multiplicity counts, it MUST call `uniform_random(owner, weighted_values)`,
- if it cannot materialize the finite weighted projection, it MUST raise an exception rather than pretend to sample correctly.

This is the key refinement over the initial informal API sketch.

Without this rule, extension-owned labels under constraints would violate the current core invariants.

## Infinite Domains

An extension domain may be infinite.

Example:

- `Regex("a*")` denotes `{ "", "a", "aa", "aaa", ... }`.

For v1, the requirements are:

- exhaustive generation over an infinite extension domain MUST raise an exception,
- `uniform_random` over an infinite admissible projection MUST raise an exception,
- `arbitrary` MAY still return a witness.

This gives extensions a practical escape hatch for witness-oriented generation without forcing the base core to solve infinite exhaustive search.

## Interaction with Search and SAT

The current search backend divides labels into:

- SAT-encodable labels,
- Python-enumerated labels.

In the first extension iteration, extension-owned leaves should be treated as solver-external labels.

That means:

- their domains come from extension hooks rather than CP-SAT variable domains,
- comparisons over them are evaluated in Python under the existing expression semantics,
- initialize may still add extra constraints over ordinary core labels,
- built-in overrides such as a custom `bool` extension remain expression-typed as booleans but need not be SAT-native in v1.

This keeps the first implementation compatible with the current architecture in `src/equivalib/core/search.py` and `src/equivalib/core/sat.py`.

Direct solver-integrated extensions are deferred.

## Interaction with Caching

The current caching document distinguishes:

- unnamed subtrees,
- guaranteed-cacheable named subtrees.

Extension-owned leaves fit that model if and only if the requested operation is itself cacheable.

Examples:

- a finite `Palette("warm")` exhaustive denotation is cacheable as an unnamed subtree,
- a finite label-closed unconstrained regex leaf is cacheable under `"all"`,
- an infinite regex leaf is not exhaustively cacheable because exhaustive generation itself is invalid,
- arbitrary witnesses may still be cacheable if the extension defines them deterministically.

This document does not add new mandatory cache guarantees beyond those already defined in [docs/caching.md](caching.md).

## Error Model

A compliant extension-aware implementation SHOULD raise `TypeError` or `ValueError` consistently with the current core style.

At minimum, the following cases must fail:

- `extensions` is not a mapping,
- an extension registry key is not a type,
- an extension object does not provide the required hook surface,
- a custom leaf appears with no matching extension,
- initialize returns a non-expression,
- initialize returns a non-boolean expression,
- an exhaustive extension operation is requested for an infinite domain,
- uniform-random selection is requested for an infinite admissible projection,
- a non-empty address path is used against an atomic extension-owned label,
- arithmetic or ordering is attempted on an opaque extension-owned label.

## Worked Examples

### Built-in override: `bool`

If the registry contains a custom extension for `bool`, then:

```python
generate(bool, extensions={bool: custom_bool_extension})
```

uses the extension-owned denotation instead of the built-in `{False, True}`.

If the same extension is used with a named occurrence:

```python
generate(
    Annotated[bool, Name("B")],
    Reference("B"),
    {"B": "arbitrary"},
    extensions={bool: custom_bool_extension},
)
```

then `Reference("B")` remains boolean-typed and the extension decides how the satisfying boolean witness is selected.

### Regex extension

Let `Regex("ab|cd")` be a custom leaf owned by a `Regex` extension.

Then:

```python
generate(Regex("ab|cd"), extensions={Regex: regex_extension})
```

must exhaustively return `{"ab", "cd"}`.

For an infinite regex:

```python
generate(Regex("a*"), extensions={Regex: regex_extension})
```

must raise an exception because exhaustive generation is infinite.

But:

```python
generate(
    Annotated[Regex("a*"), Name("R")],
    BooleanExpression(True),
    {"R": "arbitrary"},
    extensions={Regex: regex_extension},
)
```

may still return a singleton witness set such as `{""}` or `{"a"}`, depending on the extension's arbitrary-witness policy.

## Implementation Plan

The recommended implementation order is:

1. **Freeze the spec and xfail tests.**
   Add the extension acceptance scaffold before any runtime changes.

2. **Add the public API shell.**
   Extend `generate(...)` to accept `extensions=None` and add an exported `Extension` protocol or equivalent runtime validation helper.

3. **Implement the initialize pass.**
   Call every registered extension once, conjoin returned constraints, and reroute all later pipeline stages to the effective constraint.

4. **Extend normalization with `ExtensionNode`.**
   Detect matching extension-owned leaves and preserve their owner payloads in IR.

5. **Teach validation about extension kinds.**
   Enforce atomic-by-default rules, bool/int override rules, and address-path rejection for opaque extension nodes.

6. **Teach denotation and concretization about extension nodes.**
   Route unnamed exhaustive generation and named label-domain construction through `enumerate_all(owner)`.

7. **Integrate extension-aware method reduction.**
   Preserve current `apply_methods(...)` semantics by passing satisfying projections to extension `arbitrary` and `uniform_random` hooks when available.

8. **Add the first reference extension: regex.**
   Use it to validate:
   finite exhaustive generation,
   infinite exhaustive failure,
   arbitrary witness generation over infinite domains.

9. **Document solver boundaries and caching behavior.**
   Keep extension labels on the Python-enumerated side until there is a separate solver-extension design.

10. **Only after that, consider richer extension typing.**
    Addressable structured extension values and solver-native extensions should be a separate phase, not folded into the first rollout.

This order keeps the work aligned with the current implementation seams in:

- `src/equivalib/core/api.py`
- `src/equivalib/core/normalize.py`
- `src/equivalib/core/validate.py`
- `src/equivalib/core/domains.py`
- `src/equivalib/core/search.py`
- `src/equivalib/core/methods.py`
- `src/equivalib/core/sat.py`

That is the smallest implementation surface that can support extensions without silently breaking the current core guarantees.