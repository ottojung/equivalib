# Caching in equivalib Core

## Overview

This document describes the caching model for the core generation engine defined in [docs/spec1.md](docs/spec1.md).
The planned extension mechanism that may introduce extension-owned leaves is specified in [extensions.md](extensions.md).

Generation is extensional: the same subtree under the same relevant context always denotes the same value set. Caching is therefore semantically natural, not just an optimization trick.

## Definitions

### Label-closed subtrees

For a subtree `u` inside a larger tree `t`, define `labels(u)` as the set of labels occurring in `u`.

`u` is label-closed in `t` if every occurrence in `t` of every label in `labels(u)` also lies inside `u`.

Intuition:

- a label-closed subtree contains the whole meaning of its own labels
- no outside occurrence can further narrow those labels by repeated-label intersection

### Constraint-independent subtrees

A subtree `u` is constraint-independent with respect to `constraint` if:

```text
labels(u) ∩ mentioned_labels(constraint) = ∅
```

where `mentioned_labels(constraint)` is the set of labels referred to anywhere in `constraint`.

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

Therefore a compliant implementation MAY memoize and reuse the generated values of `u` across distinct enclosing results without changing observable behavior.

### Semantic cache key

For a guaranteed-cacheable subtree, the minimum correct cache key is a function of:

- the subtree itself (its complete structure), and
- the methods restricted to the labels of that subtree

Implementations MAY cache broader classes of subtrees if they can prove semantic equivalence for those broader cases.

For extension-owned leaves, this document's guarantees still apply only when the requested extension operation itself is well-defined and finite for the relevant method.

## Immediate corollaries

The following are always guaranteed-cacheable:

- unnamed subtrees (they have no labels, so label-closure and constraint-independence are trivially satisfied)
- named subtrees whose labels are local to that subtree and not mentioned in the constraint

This includes the simple case requested by the core design:

- values that do not contain anything mentioned in the constraint can be cached, provided their labels are not shared outside the subtree

## Correctness invariant

The observable outputs MUST remain exactly unchanged whether the cache is cold or warm.

Caching MUST NOT affect:

- which values appear in the output set
- the structural equality semantics used to deduplicate results
- the non-emptiness invariant for super methods

## When caching applies

### Unnamed subtrees

Every unnamed subtree is unconditionally guaranteed-cacheable because it has no labels at all. Its denotation is a pure function of its structure.

Example: the subtree `Tuple[bool, Literal["N\\A"]]` always denotes `{(True, "N\\A"), (False, "N\\A")}` regardless of context. It can be memoized by its structure alone.

### Label-closed unconstrained named subtrees

A named subtree `Annotated[T, Name("X")]` where `"X"` does not appear in the constraint and does not appear elsewhere in the enclosing tree is guaranteed-cacheable.

Its cache key is `(subtree_structure, method_for_X)`.

### Partial caching: outer context still needed

If a named subtree is label-closed but its label is mentioned in the constraint, the subtree is NOT guaranteed-cacheable in isolation. The constraint may filter the domain of that label, so the full result depends on the constraint and the rest of the tree.

In this case caching requires the full enclosing context and is generally not beneficial.

## Optional broader caching

Implementations MAY extend caching beyond the guaranteed-cacheable cases, provided they can prove that the cached result is semantically equivalent to re-computing from scratch.

Examples of potentially cacheable patterns that require proof:

- Subtrees that are label-closed but where the constraint mentions their labels, if the implementation can show that the constraint has no satisfying assignments that reach that subtree (dead constraint branches).
- Subtrees that share labels with other subtrees, if the intersection of their domains would not change the cached result.

Such extensions are optional and implementation-defined. The correctness invariant above always applies.

## Cache invalidation

A cached value for a subtree MUST be invalidated whenever:

- the subtree structure changes
- the methods assigned to the labels of that subtree change

No other changes to the enclosing tree or constraint can affect a guaranteed-cacheable subtree's output.

## Relationship to solver optimization

Caching and solving are complementary optimizations:

- **Caching** avoids redundant generation for subtrees whose output is context-independent.
- **Solving** (SAT, SMT, CP) efficiently computes the full satisfying assignment set `S0`.

A typical implementation might:

1. Identify all guaranteed-cacheable subtrees before generation starts.
2. Compute and cache their denotations independently.
3. Use a solver only for the constrained portion of the tree (the parts involving labels mentioned in the constraint).
4. Combine the solver output with the cached subtree denotations during concretization.

This decomposition is sound because guaranteed-cacheable subtrees do not interact with the constraint.

## Implementation strategies

### Memoization table

The simplest approach is a dictionary keyed by `(subtree, restricted_methods)`. Both components must be hashable. IR nodes (`IRNode`) in `equivalib.core.types` are frozen dataclasses and therefore hashable by value.

`restricted_methods` can be represented as a `frozenset` of `(label, method)` pairs, restricted to the labels in the subtree.

### Lazy evaluation

Guaranteed-cacheable subtrees can be evaluated lazily and independently of the main generation pass. This is useful when many large trees share the same unconstrained region.

### Sharing detection

At tree construction time, the implementation can scan the tree to find all guaranteed-cacheable regions, assign each a cache key, and record which regions are shared (appear in multiple enclosing trees). This allows the cache to be populated once and reused many times without re-scanning.

### Bounded cache size

For long-running applications that generate from many distinct trees, the cache may grow unboundedly. Standard cache eviction policies (LRU, TTL) can be applied. The correctness invariant still holds for any eviction policy because eviction only causes re-computation, not incorrect results.
