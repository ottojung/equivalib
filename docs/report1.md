# Report 1: Repository Study and XFAIL Analysis

## Scope

I studied the repository structure, the source modules under `src/equivalib`, the test suite, and the current XFAIL tests. I also ran the XFAIL-heavy test modules both normally and with `--runxfail` to expose the real failures.

Local baseline during this review:

- `37` tests passed
- `3` tests were skipped
- `16` tests were marked XFAIL

I did not edit library code. This report is based on repository study, runtime experiments, and git history. External web search was not available in this environment.

## Executive Summary

`equivalib` is a small constraint-guided test-data generator built around equivalence partitioning.

At a high level, it:

1. reads Python type descriptions,
2. expands them into a dependency-ordered internal form,
3. builds symbolic "sentences" of candidate values,
4. lets dataclass `__post_init__` methods impose constraints,
5. then collapses each symbolic sentence into one concrete representative.

Most of the repository already works for:

- concrete booleans, bounded integers, literals, tuples, unions, and dataclasses,
- constraints over concrete values,
- a single `Super` field,
- a `Super` field constrained against concrete values.

The XFAIL tests fail mainly because repeated `Super` fields of the same labelled type are treated as the same symbolic variable. That is an architecture problem, not just a small bug. There is also a second issue: the low-level `generate_sentences(...)` API does not provision type dependencies by itself, so some direct tests fail before symbolic reasoning even starts.

## What the Library Is Doing to Inputs

The domain idea is equivalence partitioning for structured inputs.

Instead of asking for every concrete input, the library tries to construct representative inputs from type information and constraints. For example:

- `bool` becomes two representatives: `False` and `True`.
- `Annotated[int, ValueRange(1, 9)]` becomes representatives in the bounded range.
- dataclasses become compositions of representatives of their fields.
- `Annotated[..., Super]` means "do not enumerate this field concretely yet; treat it as a symbolic variable with a bounded domain and let constraints narrow it down."

That is why the library has two phases:

- a symbolic construction phase,
- then a collapse phase that picks one satisfying concrete assignment.

This is important conceptually: `equivalib` is not trying to enumerate every satisfying model of a symbolic system. In the `Super` path it usually chooses one representative satisfying assignment per symbolic sentence.

## Repository Architecture

### User-facing pipeline

The main end-to-end entry point is `generate_instances` in `src/equivalib/generate_instances.py`.

The pipeline is:

1. `get_types_hierarchy(...)`
2. `flatten_type_hierarchy(...)`
3. `label_type_list(...)`
4. `generate_sentences(...)`
5. `arbitrary_collapse(...)`
6. yield the concrete values that were added last

In words:

- `get_types_hierarchy` recursively finds dependencies of the requested root types.
- `flatten_type_hierarchy` turns the dependency levels into a flat sequence.
- `label_type_list` converts Python type syntax into a simpler internal algebra of labelled types.
- `generate_sentences` grows symbolic candidate worlds.
- `arbitrary_collapse` asks OR-Tools for one satisfying assignment and rebuilds concrete instances.

### Type analysis layer

Important modules:

- `src/equivalib/split_type.py`: unwraps `Annotated`, `Union`, tuple types, and their metadata.
- `src/equivalib/read_type_information.py`: extracts dataclass field annotations.
- `src/equivalib/labelled_type.py`: defines the internal type algebra:
  - `BoolType`
  - `LiteralType`
  - `BoundedIntType`
  - `SuperType`
  - `UnionType`
  - `TupleType`
  - `DataclassType`
- `src/equivalib/label_type_list.py`: converts Python type forms into those labelled types.

This layer is effectively the compiler front-end of the library.

### Dependency ordering layer

Important modules:

- `src/equivalib/get_types_hierarchy.py`
- `src/equivalib/partially_order.py`
- `src/equivalib/flatten_type_hierarchy.py`

The hierarchy is multiplicity-preserving. That means the same type can appear more than once if it appears in multiple field positions. For ordinary concrete values that is mostly harmless because later structure deduplication collapses repeated identical constructions. For `Super` values that multiplicity becomes critical, because repeated occurrences are supposed to become fresh symbolic variables.

### Sentence construction layer

Important modules:

- `src/equivalib/sentence.py`
- `src/equivalib/extend_sentence.py`
- `src/equivalib/instantiate.py`
- `src/equivalib/structure.py`
- `src/equivalib/constant.py`

`Sentence` is the main intermediate representation. It contains:

- `assignments`: variable name to current value
- `structure`: variable name to structural recipe
- `reverse`: structural recipe to variable name
- `cache`: labelled type to reusable variable names
- `last`: the names introduced in the most recent expansion step
- `model`: the symbolic constraint model

`extend_sentence` is the core generator. It decides how to create candidate values for a given labelled type:

- booleans and bounded ints are enumerated concretely,
- literals are inserted as constants,
- tuples and dataclasses are built from cached sub-values,
- `SuperType` yields a symbolic placeholder.

### Constraint layer

Important modules:

- `src/equivalib/super.py`
- `src/equivalib/sentence_model.py`
- `src/equivalib/dynamic.py`
- `src/equivalib/get_current_sentence.py`

`Super` is a symbolic wrapper over an OR-Tools CP-SAT variable.

When a dataclass `__post_init__` runs inside sentence construction, comparisons such as:

- `self.y > self.x`
- `self.a != self.b`
- `self.happy == True`

do not just compute booleans. For `Super` values they add constraints into the current `SentenceModel`, then ask whether the model is still satisfiable.

That design is elegant and already works in simple cases.

### Collapse layer

Important modules:

- `src/equivalib/generic_collapse.py`
- `src/equivalib/arbitrary_collapse.py`
- `src/equivalib/random_collapse.py`

After a symbolic sentence has been accepted, collapse replaces each `Super` variable with a concrete value.

- `arbitrary_collapse` picks one satisfying assignment.
- `random_collapse` enumerates satisfying assignments and chooses one randomly.

Then `Sentence.from_structure(...)` reconstructs ordinary Python instances.

### Support and misc modules

Other modules are small and consistent with the main design:

- `mark_instance.py` / `unmark_instance.py`: attach or recover a sentence from an instance
- `instance_mark_key.py`: marker key
- `value_range.py`: integer bounds object
- `link.py`: wrapper for linked names
- `mccarthy.py`: standalone recursive example used by tests
- `all.py` and `__init__.py`: public re-export surfaces
- `scripts/ci-check.sh` and `scripts/ci-venv.sh`: CI setup and checks

## What the Tests Show About the Intended Semantics

The passing tests establish a clear intended behavior.

### What already works

- ordinary combinatorial expansion over concrete domains,
- nested dataclasses,
- tuples and unions,
- post-init assertions over concrete fields,
- simple `Super` cases with a single symbolic field,
- refinement of a single symbolic field by constraints.

Examples from the current tests:

- `Annotated[bool, Super]` yields one representative boolean instance,
- `SuperMinimalRefined` works,
- `SuperMinimalRefinedInt` works,
- non-super entangled dataclasses work.

### What the XFAILs are trying to add

The XFAIL tests all point toward the same missing capability: compound reasoning over multiple `Super` fields, especially when they have the same type.

Examples:

- two symbolic booleans constrained by inequality,
- an interval with symbolic `x` and `y` constrained by `y > x`,
- nested interval relationships,
- compound object graphs where symbolic fields must stay distinct across different object positions.

That is exactly the point where the current architecture starts to break.

## XFAIL Inventory

There are 16 current XFAIL tests across four files.

### `tests/test_generate_sentences.py`

These target the low-level symbolic sentence generator directly.

- `test_super_simple`
- `test_super_bounded`
- `test_super_entangled`
- `test_super_entangled_boring`

### `tests/test_arbitrary_collapse.py`

These target symbolic generation followed by deterministic collapse.

- `test_super_entangled`
- `test_interval`
- `test_1_overlaping_interval`
- `test_2_overlaping_intervals`
- `test_super_compound_maxgreedy1`
- plus two CI-only XFAILs that are skipped locally

### `tests/test_random_collapse.py`

- `test_super_entangled`
- `test_interval`

### `tests/test_examples.py`

These target the public `generate_instances(...)` pipeline.

- `test_super_entangled`
- `test_superpeople`
- `test_intervals`
- `test_constrained`
- `test_interval_problem`

Three of those end-to-end tests are currently placeholders with `assert False`, so they are not yet reporting live runtime behavior. `test_super_entangled` is the one that currently exposes a real end-to-end failure.

## What Fails, and Why

There are two real failure categories.

### Failure category 1: low-level direct generation is missing dependency provisioning

When the XFAIL tests call:

```python
generate_sentences(label_type_list(types))
```

directly on root dataclasses, the generator often fails with `KeyError` while trying to retrieve field values from the sentence cache.

Observed examples from `--runxfail`:

- `KeyError: SuperType(over=BoolType())`
- `KeyError: SuperType(over=BoundedIntType(...))`
- `KeyError: LiteralType(value='A')`

Why this happens:

- `generate_sentences` is currently a low-level API.
- It expects its input type sequence to already be dependency-expanded and ordered.
- `generate_instances(...)` does that expansion by calling `get_types_hierarchy(...)` and `flatten_type_hierarchy(...)` first.
- The direct XFAIL tests do not.

So for cases like `Superposed` or `Interval2`, the dataclass generator tries to build a dataclass from cached field values that do not exist yet.

This is a real limitation of the current API shape, but it is separate from the deeper `Super` identity bug.

### Failure category 2: repeated same-typed `Super` fields alias to the same symbolic variable

This is the main architectural problem.

#### The mechanism

In the full pipeline, repeated `Super` prerequisites appear in the flattened hierarchy. For example, for a dataclass like:

```python
@dataclass(frozen=True)
class SuperEntangled:
    a: Annotated[bool, Super]
    b: Annotated[bool, Super]
```

the flattened prerequisites contain two identical `Annotated[bool, Super]` entries before the dataclass itself.

That sounds correct, because there are two field positions.

But `extend_sentence` creates the same structural marker for every top-level `SuperType` occurrence:

- constructor: `LT.SuperType`
- signature: the same labelled `SuperType`
- arguments: empty tuple

Then `Sentence.insert_value(...)` consults `reverse`, which deduplicates by `Structure` equality.

So the second symbolic field does not allocate a fresh symbolic variable. It reuses the first one.

That means:

- `a` and `b` in `SuperEntangled` become the same CP-SAT variable,
- `x` and `y` in `Interval` become the same CP-SAT variable,
- identical symbolic fields deep inside larger graphs also alias.

#### The consequence

Once two logically distinct fields alias to the same variable, many intended constraints become impossible.

Examples:

- `assert self.a != self.b` becomes `v != v`, which is unsatisfiable.
- `assert self.y > self.x` becomes `v > v`, which is unsatisfiable.

The candidate sentence is therefore rejected during construction, and no sentence survives to collapse.

This exactly matches the observed end-to-end behavior:

- `generate_instances(SuperEntangled)` returns `[]`
- `generate_instances(Interval)` returns `[]`
- nested interval examples also return no sentences

#### Concrete runtime evidence

I instrumented the pipeline step by step.

For `SuperEntangled`, the sentence evolution is effectively:

1. first `SuperType` creates one symbolic variable,
2. second `SuperType` leaves the sentence unchanged instead of adding another variable,
3. dataclass construction produces zero valid sentences.

For `Interval`, the same pattern occurs:

1. first symbolic int is created,
2. second symbolic int aliases to the first,
3. `y > x` becomes unsatisfiable,
4. zero sentences survive.

That is the central reason the XFAIL family fails.

## A Subtle but Important Inconsistency in the Current Code

`Sentence.add_to_cache(...)` contains logic that appears to be trying to skip caching `Super` values:

```python
(_, _, annot) = split_type(sig)
if LT.SuperType in annot:
    return
```

However, `sig` is now a `LabelledType` object, not a raw `Annotated[...]` type form. So `split_type(sig)` does not recover `Super` annotations here, and that branch never fires in practice.

This matters because it suggests the implementation is in an inconsistent middle state:

- the current runtime behavior does cache `Super` values by labelled type,
- the code appears to have intended not to,
- but the deduplication mechanism still treats repeated symbolic occurrences as the same structure.

Git history supports that interpretation:

- the commit `a847176` moved the code toward `LabelledType`-based representations,
- later, commit `05a6cfa` added the `split_type(sig)` / `LT.SuperType in annot` check,
- but that check no longer matches the actual representation flowing through the sentence cache.

So the current architecture is not just incomplete. It is also internally conflicted about whether a `Super` value is:

- a reusable cached value,
- a fresh symbolic variable occurrence,
- or both.

It cannot safely be both.

## Why Some `Super` Cases Already Work

This is useful because it narrows the true fault line.

The symbolic pipeline itself is not fundamentally broken.

Cases that work today:

- one symbolic field alone,
- one symbolic field constrained against constants,
- one symbolic field embedded in a dataclass,
- two symbolic fields when they are forced to have different signatures.

As an experiment, a locally defined dataclass with:

- `x: Annotated[int, ValueRange(1, 8), Super]`
- `y: Annotated[int, ValueRange(2, 9), Super]`
- constraint `y > x`

generated a valid instance successfully.

That result is important. It shows that:

- OR-Tools integration is fine,
- collapse is fine for distinct symbolic variables,
- post-init constraints over symbolic values are fine,
- the real defect is identity management for repeated same-signature symbolic fields.

## Architectural Assessment

The missing concept is not "support for `Super` values" in the broad sense.

The missing concept is:

> fresh symbolic identity separate from structural type identity.

Right now the system conflates three different ideas:

1. structural equality of concrete generated values,
2. cacheability by labelled type,
3. identity of a symbolic variable occurrence.

That conflation is acceptable for ordinary concrete structures and disastrous for symbolic variables.

For a symbolic field, two occurrences with the same type usually mean:

- same domain,
- same type,
- but different variable identity.

The current sentence representation has no first-class way to express that distinction.

## Options to Solve This

### Option A: minimal targeted fix

Make every `Super` occurrence fresh, even when its labelled type matches a previous one.

Concretely, that means one of these approaches:

- bypass `reverse` deduplication for `LT.SuperType`, or
- include a unique occurrence token in the `Structure` of each new `Super` value.

Pros:

- probably fixes the active end-to-end XFAILs quickly,
- small surface-area change,
- preserves most of the current pipeline.

Cons:

- introduces `Super` as a special case inside a structure model that was built for structural reuse,
- leaves the conceptual model muddy,
- makes future symbolic extensions harder.

This is the smallest plausible repair, but probably not the cleanest long-term architecture.

### Option B: recommended redesign

Separate symbolic variables from reusable structural values.

Recommended direction:

- keep structural caching and `reverse` deduplication for ordinary concrete terms,
- introduce an explicit symbolic-variable record for `Super` occurrences,
- give each symbolic variable a unique identity regardless of type equality,
- let caches store references to symbolic candidates by domain/type, not by pretending the variable itself is a reusable structure.

In practice, `Sentence` would track two different kinds of things:

1. structural value nodes,
2. symbolic variable nodes.

Each symbolic variable node should carry at least:

- unique variable id,
- labelled type / domain,
- generated display name,
- optional provenance such as field path.

Pros:

- matches the real semantics of symbolic variables,
- naturally handles repeated same-typed symbolic fields,
- makes nested symbolic object graphs easier to reason about,
- reduces reliance on accidental interactions between `cache`, `reverse`, and `Structure` equality.

Cons:

- larger refactor,
- touches `Sentence`, `extend_sentence`, and collapse logic.

This is the option I would recommend if the goal is robust compound symbolic support rather than a narrow patch.

### Option C: clarify the public API boundary

Decide whether `generate_sentences(...)` is:

- a low-level internal API that expects dependency-expanded labelled types, or
- a public API that should accept root types directly.

Right now the repository behaves like the first, while some XFAIL tests expect the second.

Two reasonable choices:

- keep `generate_sentences` low-level and document it clearly,
- or add a public wrapper that performs hierarchy expansion automatically before sentence generation.

If the XFAIL tests are considered valid public expectations, this API split needs to be addressed explicitly.

### Option D: clean up hierarchy multiplicity after the `Super` redesign

After symbolic identity is fixed, it would be worth revisiting whether duplicate entries from `get_types_hierarchy(...)` should remain as-is, be normalized, or be represented more explicitly as field-position requirements.

This is not the main blocker today, but it is part of why the current behavior is hard to reason about.

## Recommended Implementation Order

If this repository were going to tackle the problem now, I would do it in this order.

1. Decide the intended public contract of `generate_sentences(...)`.
2. Introduce fresh symbolic identity for `Super` occurrences as a first-class concept.
3. Only after that, adjust cache and dedup behavior to match the new model explicitly.
4. Add focused regression tests for repeated same-typed `Super` fields:
   - same dataclass,
   - nested dataclasses,
   - satisfiable and unsatisfiable relations,
   - interval-style ordering constraints.
5. Re-enable the current XFAIL tests one group at a time.

## Expected Coverage of the Current XFAILs

If Option B is implemented well, I would expect it to address the real runtime blockers behind:

- `test_super_entangled` in all four test files,
- `test_interval`,
- `test_1_overlaping_interval`,
- `test_2_overlaping_intervals`,
- `test_super_compound_maxgreedy1`,
- the more complex interval-style CI-only XFAILs.

The placeholder tests in `tests/test_examples.py` would still need real expected results and likely some performance review, but the architecture would finally be pointed in the right direction.

The direct `generate_sentences(...)` XFAILs would additionally require either:

- dependency auto-provisioning, or
- a documented test change so they use the higher-level pipeline.

## Bottom Line

The repository already has a coherent core idea and a mostly working symbolic pipeline.

The XFAILs are failing because the current sentence representation does not distinguish:

- "another variable of the same symbolic type"

from:

- "the same symbolic variable seen again."

That distinction is exactly what compound `Super` support needs.

So yes: this probably does require an architecture change.

The narrowest useful formulation of that change is:

> treat `Super` occurrences as fresh symbolic identities, not as structurally reusable values.

Once that is true, the rest of the current design has a reasonable chance of supporting the XFAIL scenarios.