# Plan 1: Implementing the Spec 1 Core

## Goal

Implement the core specified in [docs/spec1.md](docs/spec1.md) as a new, self-contained value-tree engine.

The new core must:

- operate on finite value trees rather than sentence objects,
- use `Name(label)` as the only source of symbolic identity,
- use `Expression` AST values rather than source-text constraints,
- expose the single public interface

```python
generate(tree: Type[T], constraint: Expression = BooleanExpression(True), methods: Mapping[Label, Method] = {}) -> Set[T]
```

- satisfy the non-emptiness invariant for all non-`"all"` methods,
- implement the guaranteed caching rules from the spec,
- be testable independently of the current legacy implementation.

## Executive Decision

The new core must be implemented beside the existing engine, not inside it.

The current engine is centered on:

- `Sentence` mutation,
- structural deduplication,
- Python object instantiation,
- `__post_init__` assertions,
- OR-Tools-backed symbolic collapse.

That is a different architecture from the spec. Trying to morph the current engine into the new core would preserve the wrong abstractions and create hidden incompatibilities.

Therefore the plan is:

1. build a new `equivalib.core` package,
2. keep the old engine untouched while the new core is stabilized,
3. only later decide how legacy APIs should compile down to the new core.

## Current Codebase Assessment

### Components that should be reused

These are aligned enough with the new core to reuse directly or with very light wrapping:

- `src/equivalib/value_range.py`
- `src/equivalib/split_type.py`

`ValueRange` remains part of the public tree syntax, and `split_type` is still the right low-level helper for inspecting `Annotated`, `Union`, `Tuple`, and `Literal` forms.

### Components that should not be reused inside the new core

These belong to the legacy sentence engine and should be treated as deprecated implementation strategy, not as a foundation for the new core:

- `src/equivalib/labelled_type.py`
- `src/equivalib/label_type_list.py`
- `src/equivalib/get_types_hierarchy.py`
- `src/equivalib/flatten_type_hierarchy.py`
- `src/equivalib/generate_sentences.py`
- `src/equivalib/extend_sentence.py`
- `src/equivalib/sentence.py`
- `src/equivalib/sentence_model.py`
- `src/equivalib/super.py`
- `src/equivalib/generic_collapse.py`
- `src/equivalib/arbitrary_collapse.py`
- `src/equivalib/random_collapse.py`
- `src/equivalib/generate_instances.py`

### Why the legacy engine is not the right base

The legacy engine has three structural mismatches with the spec.

1. It models generation as mutation of a sentence state rather than denotation of finite trees.
2. It binds symbolic identity to structural reuse and variable allocation, whereas the spec binds identity only to `Name(label)`.
3. It relies on Python execution of `__post_init__` and overloaded comparisons, whereas the spec requires explicit `Expression` AST evaluation.

Because of that, the correct implementation path is replacement-by-parallel-construction, not incremental patching.

## Non-Ambiguous Design Decisions

The following choices should be implemented exactly.

### Public API placement

The new core should live at:

- `equivalib.core.generate`

and export the AST constructors and `Name` from the same package.

The old top-level `equivalib.generate_instances` API should not be rewritten in phase 1.

### Supported tree language in v1

The core should support exactly what the spec currently covers:

- `bool`
- `None`
- `Literal[...]`
- `Tuple[...]`
- `Union[...]`
- `Annotated[int, ValueRange(...)]`
- `Annotated[..., Name(label)]`

Dataclasses are out of scope for v1 core.

### Internal representation

Normalize user-facing typing objects into an explicit IR with these nodes:

- `NoneNode`
- `BoolNode`
- `LiteralNode(value)`
- `IntRangeNode(min_value, max_value)`
- `TupleNode(items)`
- `UnionNode(options)`
- `NamedNode(label, inner)`

This is the canonical implementation representation. It must not use raw `typing` objects after normalization.

### Expression representation

Use explicit AST dataclasses for:

- `BooleanConstant`
- `IntegerConstant`
- `Reference`
- `Neg`
- `Add`
- `Sub`
- `Mul`
- `FloorDiv`
- `Mod`
- `Eq`
- `Ne`
- `Lt`
- `Le`
- `Gt`
- `Ge`
- `And`
- `Or`

`BooleanExpression(True)` should be implemented as a tiny convenience constructor that returns `BooleanConstant(True)`.

### Canonical deterministic order

Deterministic selection requires a total order on runtime values.

The implementation must use:

- booleans: `True` before `False`
- integers: ascending numeric order
- strings: lexicographic ascending order
- `None`: before tuples and after primitive scalars is acceptable, but the chosen place must be fixed and documented in code
- tuples: lexicographic under the same element ordering

The simplest total-order key is:

1. kind rank
2. value recursively within kind

with a fixed kind rank table.

### Label processing order

Process labels in ascending lexicographic order of the label string.

This applies to:

- satisfying-assignment search variable order
- application order of super methods

### Method semantics

`"all"`:

- preserve all satisfying variation for that label

`"arbitrary"`:

- deterministic
- choose the first projected value under canonical value order

`"uniform_random"`:

- choose projected values with probability proportional to the number of satisfying assignments supporting that value

`"arbitrarish_randomish"`:

- non-deterministic
- choose uniformly from the distinct projected values, not weighted by assignment counts

This last decision is intentional. It gives useful variation while remaining fast and easy to explain.

### Address validity

Address paths in `Reference(label, path)` must be validated statically against the denotation shape of the named subtree.

If a label can denote a non-tuple anywhere along the address path, the reference is invalid and generation must fail before search starts.

### Caching guarantee boundary

Only the guaranteed-cacheable cases from the spec are mandatory in v1:

- unnamed subtrees
- subtrees that are both label-closed and constraint-independent

Any broader caching is optional.

### Solver strategy

Phase 1 should use exact finite search with partial-evaluation pruning, not a SAT or CP backend.

SAT/SMT/CP-SAT may be added later as an accelerator, but not as the first implementation.

## Target Package Structure

Create the following modules.

- `src/equivalib/core/__init__.py`
- `src/equivalib/core/api.py`
- `src/equivalib/core/types.py`
- `src/equivalib/core/expression.py`
- `src/equivalib/core/normalize.py`
- `src/equivalib/core/validate.py`
- `src/equivalib/core/domains.py`
- `src/equivalib/core/eval.py`
- `src/equivalib/core/order.py`
- `src/equivalib/core/search.py`
- `src/equivalib/core/methods.py`
- `src/equivalib/core/cache.py`

Add a shared `Name` definition at one of these locations:

- `src/equivalib/core/name.py`, or
- `src/equivalib/name.py`

The cleaner choice is `src/equivalib/core/name.py` and re-export it from `equivalib.core`.

## TDD Operating Rule

This plan must be executed as strict red-green-refactor.

For every phase in this document:

- Red: add or tighten the smallest failing test slice that captures the target behavior or the relevant `GEN-*` rows.
- Green: implement only the minimum code needed to make that new slice pass.
- Refactor: improve names, structure, and internal factoring while keeping the whole previously-green suite green.

No production module work should begin before its failing tests exist. No phase is complete until both the new slice and the full accumulated suite are green.

## TDD Phase-by-Phase Implementation Plan

Each phase below names the production goal, but execution order is always tests first, then code, then refactoring.

### Phase 1: Create the public shell

Implement:

- `Name`
- all `Expression` AST classes
- `BooleanExpression`
- `generate` as a stub that raises `NotImplementedError`

Export them from `equivalib.core`.

Purpose:

- make the TDD tests importable early,
- establish the exact public names before filling semantics.

### Phase 2: Implement normalized tree IR

In `core/types.py`, add immutable dataclasses for the normalized IR.

Rules:

- every node must be hashable,
- equality must be structural,
- all later caching depends on this.

Add helpers:

- `labels(node)`
- `contains_name(node)`
- `tree_shape(node)` or equivalent structural descriptor for address validation

### Phase 3: Normalize `Type[T]` into the IR

In `core/normalize.py`:

1. use `split_type` to inspect incoming types,
2. normalize every valid tree into the IR,
3. reject invalid forms immediately.

Normalization rules:

- `bool` -> `BoolNode()`
- `None` -> `NoneNode()`
- `Literal[x]` -> `LiteralNode(x)`
- `Annotated[int, ValueRange(a, b)]` -> `IntRangeNode(a, b)`
- `Union[...]` -> `UnionNode(...)`
- `Tuple[...]` -> `TupleNode(...)`
- `Annotated[base, ..., Name(label), ...]` -> `NamedNode(label, normalized_base)`

For `Annotated[...]`:

- peel out `ValueRange`
- peel out `Name`
- reject duplicates
- reject unknown metadata in v1 core

### Phase 4: Validate trees, methods, and expressions

In `core/validate.py`, implement three validators.

#### Tree validator

Reject:

- empty labels
- plain `int`
- invalid ranges
- multiple `ValueRange`
- multiple `Name`

#### Method validator

Reject:

- method keys not present in the tree
- method strings outside the four supported literals

#### Expression validator

Validate against the tree:

- every referenced label exists
- every address path is statically valid
- operator operands have valid types

This validator must run before generation starts.

### Phase 5: Implement unnamed denotation

In `core/domains.py`, implement:

- `values(node)` for name-free nodes

This is a pure finite denotation function.

Required behavior:

- `BoolNode` -> `{True, False}`
- `LiteralNode(v)` -> `{v}`
- `IntRangeNode(a, b)` -> `{a, ..., b}`
- `UnionNode` -> set union of branch denotations
- `TupleNode` -> cartesian product of item denotations

This function is also the base engine for label-domain intersection.

### Phase 6: Implement label domains

Still in `core/domains.py`, implement:

- collection of all named occurrences
- `domain(label)` = intersection of denotations of all occurrences of that label
- `domain_map(tree)` returning all label domains at once

If any domain is empty, generation returns the empty set immediately.

### Phase 7: Implement expression evaluation

In `core/eval.py`, implement:

- `eval_expression(expr, assignment)`
- `eval_expression_partial(expr, partial_assignment)`

Use a three-valued partial result:

- `True`
- `False`
- `Unknown`

Partial evaluation rules must support short-circuit pruning.

Examples:

- `And(False, Unknown)` -> `False`
- `And(True, Unknown)` -> `Unknown`
- `Or(True, Unknown)` -> `True`
- `Or(False, Unknown)` -> `Unknown`

This is required so the exact search does not degenerate into full brute force for every problem.

### Phase 8: Implement exact satisfying-assignment search

In `core/search.py`, implement backtracking search over labels.

Algorithm:

1. compute the label set in lexicographic order,
2. compute `domain_map(tree)`,
3. assign labels one by one,
4. iterate domain values in canonical value order,
5. run partial expression evaluation after each extension,
6. prune on `False`,
7. accept only complete assignments where the expression evaluates to `True`.

Return the exact satisfying assignment set `S0`.

This is the reference semantics implementation.

### Phase 9: Implement super methods

In `core/methods.py`, implement the reduction from `S0` to `S*`.

Algorithm:

1. start with `S := S0`,
2. process labels in lexicographic order,
3. skip labels whose effective method is `"all"`,
4. for the others, compute `projection(label, S)`,
5. choose a witness according to the method,
6. filter `S` to assignments consistent with that witness.

Required policies:

- `"all"`: no filtering
- `"arbitrary"`: choose first value under canonical order
- `"uniform_random"`: weighted by assignment counts
- `"arbitrarish_randomish"`: uniform over distinct projected values

The non-emptiness invariant is automatic if witness selection is always from the live projection.

### Phase 10: Implement concretization

In `core/api.py` or a small helper module, implement:

- `concretize(node, assignment)`

Rules:

- unnamed nodes expand fully
- `NamedNode(label, inner)` collapses atomically to `assignment[label]`

This is what makes a named tuple behave as one variable rather than as independent component labels.

### Phase 11: Implement caching

In `core/cache.py`, implement:

- `mentioned_labels(expr)`
- `is_label_closed(subtree, whole_tree)`
- `is_constraint_independent(subtree, constraint)`
- `is_guaranteed_cacheable(subtree, whole_tree, constraint)`
- `CacheStats`
- cache storage keyed by semantic cache keys

Mandatory caches:

1. unnamed subtree denotation cache
2. guaranteed-cacheable subtree generation cache

Required cache key contents for guaranteed-cacheable subtrees:

- normalized subtree
- methods restricted to `labels(subtree)`

Do not include the whole tree or full constraint in this key for guaranteed-cacheable cases.

### Phase 12: Final public `generate`

In `core/api.py`, implement the full pipeline:

1. normalize the incoming `Type[T]`
2. validate tree, methods, and expression
3. compute label domains
4. search exact satisfying assignments `S0`
5. apply super-method reductions to get `S*`
6. concretize each assignment into runtime values
7. union the results into a Python `set`

This function should be pure from the caller’s perspective.

### Phase 13: Export stabilization

Once the core passes all new tests, export from:

- `equivalib.core`

Do not rewrite legacy top-level generation APIs in this phase.

## Testing Plan

### Principle

The test suite for the new core must be spec-driven, not legacy-driven.

It must also be implementation-driving, not implementation-following.

That means:

- every new behavior starts life as a failing or `xfail` test,
- when a phase begins, its targeted tests are converted from expected-failure scaffolding into normal red tests,
- production code is written only after the red tests are in place,
- refactors are allowed only after that phase is green.

The existing super-related tests in:

- `tests/test_generate_sentences.py`
- `tests/test_arbitrary_collapse.py`
- `tests/test_random_collapse.py`
- `tests/test_examples.py`

are useful historical evidence, but they are written for the old dataclass and sentence engine. They must not be the acceptance suite for the new core.

### New test layout

Create or evolve the new core tests under:

- `tests/test_core.py`

and later, if the suite grows large, split it into:

- `tests/core/test_normalize.py`
- `tests/core/test_validate.py`
- `tests/core/test_expression.py`
- `tests/core/test_values.py`
- `tests/core/test_domains.py`
- `tests/core/test_search.py`
- `tests/core/test_methods.py`
- `tests/core/test_cache.py`
- `tests/core/test_generate.py`
- `tests/core/test_spec_compliance.py`

### Required test groups

#### Group 1: public import surface

Test that the new core exports:

- `generate`
- `Name`
- `BooleanConstant`
- `BooleanExpression`
- `IntegerConstant`
- `Reference`
- `Eq`, `Ne`, `Lt`, `Le`, `Gt`, `Ge`
- `And`, `Or`
- arithmetic nodes

#### Group 2: normalization and validation

Test:

- valid trees from the spec
- empty label rejection
- plain `int` rejection
- duplicate `Name` rejection
- duplicate `ValueRange` rejection
- unknown method key rejection
- reference to missing label rejection
- invalid address rejection

#### Group 3: unnamed denotation

Test exact output for:

- literals
- booleans
- bounded integers
- tuples
- unions

#### Group 4: label domains

Test:

- single occurrence domain
- repeated label intersection
- empty repeated-label intersection
- named tuple domains

#### Group 5: expression evaluation

Test:

- arithmetic nodes
- equality and inequality
- boolean conjunction and disjunction
- tuple-addressed references
- partial evaluation pruning cases

#### Group 6: exact search

Test:

- unconstrained one-label search
- equality and inequality constraints
- addressed tuple constraints
- arithmetic constraints
- contradictory constraints

#### Group 7: method behavior

Test:

- `"all"` exhaustiveness
- `"arbitrary"` determinism
- `"arbitrary"` singleton output
- `"uniform_random"` subset-of-all property
- `"arbitrarish_randomish"` subset-of-all property
- non-emptiness under all super methods when the exhaustive problem is satisfiable

#### Group 8: caching

Test with instrumentation:

- cache hits for unnamed reused subtrees
- cache hits for guaranteed-cacheable named subtrees
- identical outputs on cold and warm runs
- no semantic dependence on unrelated outer context for guaranteed-cacheable subtrees

### Acceptance criterion

The spec compliance matrix in [docs/spec1.md](docs/spec1.md) is the acceptance contract.

Every `GEN-*` item must correspond to at least one direct automated test.

The suite should maintain an explicit phase-to-test mapping so that each implementation slice has a known red entry point and a known green exit condition.

No implementation phase is complete until the matching compliance rows are green.

## Implementation Order

The order below is mandatory, and each item is a red-green-refactor slice rather than a code-first milestone.

1. Red: expand Group 1 tests for the public import surface and convenience constructors.
2. Green: create `equivalib.core`, the AST shells, `Name`, `BooleanExpression`, and a stub `generate`.
3. Refactor: stabilize package exports and import ergonomics.
4. Red: expand Group 2 tests for normalization and validation, including duplicate metadata, unknown metadata, method validation, and invalid addresses.
5. Green: implement normalized tree IR, normalization, and validation together so invalid inputs fail before search starts.
6. Refactor: extract shared tree-shape and validation helpers.
7. Red: expand Group 3 and Group 4 tests for unnamed denotation, unions, `None`, repeated-label intersections, and atomic named tuples.
8. Green: implement unnamed denotation and label-domain intersection.
9. Refactor: separate pure domain logic from API glue and cache-facing helpers.
10. Red: expand Group 5 and Group 6 tests for arithmetic AST evaluation, address evaluation, contradictions, and partial-pruning cases.
11. Green: implement expression evaluation and exact satisfying-assignment search.
12. Refactor: simplify partial evaluation and canonical ordering internals.
13. Red: expand Group 7 tests for determinism, singleton-subset behavior, and the non-emptiness invariant across all super methods.
14. Green: implement super-method reduction and concretization.
15. Refactor: tighten witness-selection and assignment-filtering code paths.
16. Red: add Group 8 cache instrumentation tests plus any remaining uncovered `GEN-*` rows.
17. Green: implement guaranteed-cacheable subtree caching, `CacheStats`, and the final public `generate` pipeline.
18. Refactor: freeze exports, run the full compliance sweep, and document the cache boundary in code.

This order prevents circular design drift and makes every phase start from an observable failing behavior.

## Definition of Done

The new core is done when all of the following are true.

1. `equivalib.core.generate` exists and matches the spec signature.
2. The new core passes the complete `tests/test_core.py` suite without relying on phase-level `xfail` scaffolding.
3. The compliance behaviors from [docs/spec1.md](docs/spec1.md) are all covered and passing.
4. Guaranteed-cacheable subtree reuse is demonstrable through instrumentation.
5. The implementation does not depend on the old `Sentence` / `Super` engine.
6. Legacy APIs remain unchanged until a deliberate follow-up migration phase.

## Immediate Next Action

The immediate next implementation step is:

1. finish mapping the current `tests/test_core.py` coverage to the `GEN-*` matrix, including the remaining cache-specific cases,
2. turn Group 1 from scaffolding into normal red tests,
3. implement only the public shell needed to make Group 1 green,
4. continue phase-by-phase in the red-green-refactor order above.