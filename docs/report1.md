# Report 1: XFAIL Analysis and Remediation Options

## Scope and method

I reviewed the full repository (`src/`, `tests/`, `README`, scripts, and packaging metadata), then focused on all tests marked with `@pytest.mark.xfail(reason="No supervalue support yet.")`.

Because `ortools` is not available in this execution environment, I could not run the suite to observe runtime failures directly. The analysis below is therefore based on static code inspection and test intent.

## Repository architecture (high-level)

Equivalib has a two-phase pipeline:

1. **Type expansion / symbolic sentence building**
   - Types are discovered and partially ordered (`get_types_hierarchy`, `flatten_type_hierarchy`).
   - Python type hints are converted into internal labelled types (`label_type_list`, `label_type`).
   - `generate_sentences` + `extend_sentence` construct `Sentence` objects that cache reusable values and build dataclass instances.
   - `Annotated[..., Super]` fields become symbolic `Super(...)` objects whose constraints are accumulated through dataclass `__post_init__` assertions.

2. **Collapse to concrete values**
   - `arbitrary_collapse` and `random_collapse` use OR-Tools CP-SAT to assign each super-variable a concrete value.
   - `generic_collapse` rewrites structures and rebuilds a concrete `Sentence` via `Sentence.from_structure`.
   - `generate_instances` returns only the "last" generated values, after collapse.

This split is central to the XFAIL behavior.

## Inventory of XFAIL tests

I found 19 XFAIL tests:

- `tests/test_generate_sentences.py`: 4
- `tests/test_arbitrary_collapse.py`: 8
- `tests/test_random_collapse.py`: 2
- `tests/test_examples.py`: 5

All use the same reason string: **"No supervalue support yet."**

## Why these tests fail (root causes)

## 1) Symbolic supervalues are intentionally excluded from reuse/cache

`Sentence.add_to_cache` skips signatures annotated with `Super`.
That means symbolic fields are not treated as reusable values during sentence expansion, unlike ordinary bool/int/dataclass values.

**Impact:** generation does not get a first-class symbolic-domain model for reuse/equivalence during expansion; instead, supervalues remain opaque placeholders until collapse.

## 2) `generate_sentences` is not a full symbolic constraint enumerator

In `extend_sentence`, when a model already has supervariables (`is_based_on_super`), the function clones per input and yields each successful extension. But the super domain is not enumerated there; it only checks satisfiability incrementally through `Super` comparison operators.

**Impact:** tests expecting a canonical, fully supported symbolic super semantics at generation time (especially counts/dedup assumptions) are fragile or currently unsupported.

## 3) Collapse happens after generation, not during generation

`generate_instances` always calls `arbitrary_collapse` for each sentence.
So super support is strongest at the **instance** layer, not the `generate_sentences` layer.

**Impact:** many tests in `test_examples.py` (which use `generate_instances`) for *simple* super use-cases already pass, while several tests in `test_generate_sentences.py` remain XFAIL because they assert expectations directly on symbolic sentence content/shape.

## 4) `random_collapse` enumerates all SAT solutions globally, then samples

`RandomCollapser` collects all solver assignments for all supervariables and then picks one random assignment.

**Impact:** for larger cases, this is expensive and unstable for deterministic expectation tests; also it is not architecture for scalable "supervalue support" in complex coupled models.

## 5) Several XFAIL tests are placeholders/TODOs, not just failing checks

In `tests/test_examples.py`, multiple XFAIL tests contain `assert False` before the real assertions (`test_superpeople`, `test_intervals`, `test_constrained`, `test_interval_problem`).

**Impact:** these are explicit stubs. Even with better super support, these tests fail until rewritten.

## 6) Constraint model is embedded in Python object construction side-effects

Super constraints are produced by evaluating dataclass `__post_init__` assertions while a dynamic environment (`denv`) points to the active sentence/model.

**Impact:** architecture couples instance construction and solver-model mutation. This makes behavior difficult to reason about for nested/compound super interactions and complicates deterministic enumeration semantics.

## 7) The model API only supports bool/int super primitives

`label_type` allows `Super` only for `int` and `bool` annotations.
`SentenceModel.add_variable` likewise supports bounded int / bool only.

**Impact:** complex super scenarios in tests are achieved indirectly through dataclasses containing super fields; there is no richer symbolic object model (e.g., symbolic dataclass identity or structural equalities), limiting support depth.

## Key pattern across XFAIL files

The XFAIL set is best read as **"supervalue support exists for basic constrained instantiation, but not as a complete architecture for symbolic generation + deterministic exhaustive behavior across compound structures"**.

That interpretation is consistent with:
- Passing non-XFAIL super tests in `test_examples.py` for minimal cases.
- XFAIL concentration in sentence-level and complex collapse behavior.
- Placeholder `assert False` in several complex example tests.

## Remediation options (researched design options)

## Option A — Minimal stabilization (low risk, low payoff)

- Keep current architecture.
- Reclassify tests:
  - Convert placeholder XFAIL tests to `skip` with explicit TODO issue links.
  - Narrow sentence-level super expectations to properties that current architecture actually guarantees.
- Add deterministic seed controls + avoid exact string matching where not guaranteed.

**Pros:** quick, low code churn.
**Cons:** does not deliver full supervalue architecture; technical debt remains.

## Option B — Intermediate: explicit symbolic layer in `Sentence` (recommended)

Introduce a first-class symbolic representation for supervariables and constraints:

- `Sentence` gains explicit symbolic metadata:
  - variable registry,
  - constraint list,
  - provenance links to structures.
- `extend_sentence` manipulates this symbolic state directly rather than relying mainly on post-init side-effects.
- Collapse strategies consume this canonical symbolic state.
- Cache semantics become explicit for symbolic vs concrete values.

**Pros:** fixes conceptual gap while preserving much of current API surface.
**Cons:** moderate refactor across generation, collapse, and serialization/printing.

## Option C — Full IR/solver-first redesign (high risk, highest payoff)

Move to an internal IR (typed term graph + constraint graph), then:

1. Build IR from type declarations.
2. Add constraints from constructors/assertions as typed predicates.
3. Solve/enumerate with pluggable strategies.
4. Materialize Python instances only at the boundary.

**Pros:** clean semantics, scalability, deterministic enumeration policies, easier future features.
**Cons:** substantial rewrite; migration complexity.

## Concrete implementation ideas for Option B

1. **Define symbolic term types**
   - `SymbolicVar(name, domain)`
   - `SymbolicExpr(op, args)`
   - `Constraint(expr)`

2. **Separate construction from assertion effects**
   - keep current dynamic execution path for compatibility,
   - but capture constraints into explicit symbolic structures immediately.

3. **Canonicalize and hash constraints**
   - enables deterministic dedup and reliable sentence equality.

4. **Replace global "enumerate all solutions then choose" in random collapse**
   - either sample by randomized decision heuristic,
   - or enumerate with bounded limit / streaming to avoid memory blow-ups.

5. **Introduce capability flags in tests**
   - e.g., `supports_symbolic_sentence_equivalence`, `supports_compound_super_enumeration`
   - so expected behavior tracks implemented architecture stage.

## Suggested migration plan

### Phase 0 (test hygiene)
- Remove placeholder `assert False` XFAIL stubs.
- Keep only executable XFAILs tied to concrete missing capability.

### Phase 1 (symbolic state extraction)
- Add explicit symbolic state to `Sentence`.
- Keep old APIs and make collapse consume new state.

### Phase 2 (deterministic semantics)
- Define stable ordering/canonicalization for generated sentences.
- Update tests to assert semantic equivalence rather than brittle string order when appropriate.

### Phase 3 (performance/scaling)
- Rework random collapse sampling strategy.
- Add CI benchmarks on high-cardinality super cases.

## Bottom line

The current codebase already supports **basic super constraints** in many `generate_instances` flows, but XFAIL tests reveal that **supervalue support is not yet a complete, first-class architecture at symbolic sentence generation and complex composition levels**.

The likely correct direction is indeed an architecture change (Option B minimum, Option C ideal long-term), not isolated bug fixes.
