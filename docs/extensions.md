# Extensions for equivalib Core

This document specifies the extension mechanism of `equivalib.core.generate`.

An extension owns one or more leaf syntaxes in the generation tree. It may define custom finite or infinite domains for those leaves, override built-in leaves such as `bool` and `int`, add derived constraints during initialization, and provide method-specific witness selection.

Extensions are leaf-level constructs. They do not introduce new expression nodes, and they do not make extension-owned values addressable below the whole leaf unless the leaf is one of the built-in override kinds defined in this document.

## Public API

The public entry point is:

```python
def generate(
    tree: Type[GenerateT],
    constraint: Expression = _DEFAULT_CONSTRAINT,
    methods: Optional[Mapping[Label, Method]] = None,
    extensions: Optional[Mapping[Type[A], Extension[A]]] = None
) -> set[GenerateT]:
```

Semantics:

- `methods` defaults to `{}`.
- A label not present in `methods` uses method `"all"`.
- `extensions` defaults to `{}`.
- If `extensions` is empty, generation uses only the built-in core leaf language.
- If `extensions` is present, built-in and extension-owned leaves may appear in the same tree.
- The result is the set of all runtime values of `tree` that satisfy the effective constraint and the method rules.

## Extension Protocol

`GenerateT`, `T`, and `A` are type variables.

An extension must provide exactly these methods:

```python
class Extension(Protocol[A]):
    def initialize(self, tree: Type[T], constraint: Expression) -> Optional[Expression]:
        ...

    def enumerate_all(self, tree: Type[T], constraint: Expression, address: Optional[str]) -> Iterator[A]:
        ...

    def arbitrary(self, tree: Type[T], constraint: Expression, address: Optional[str]) -> Optional[A]:
        ...

    def uniform_random(self, tree: Type[T], constraint: Expression, address: Optional[str]) -> Optional[A]:
        ...
```

Semantics:

- `initialize` is called once per registered extension.
- `enumerate_all` returns the admissible values for the addressed occurrence under the effective problem when exhaustive generation is required.
- `arbitrary` returns one admissible witness value for the addressed occurrence, or `None` if no admissible value exists.
- `uniform_random` returns one admissible witness value for the addressed occurrence, or `None` if no admissible value exists, using the same probability semantics as core `uniform_random`.

All hooks other than `initialize` operate on the effective problem produced by the initialization phase.

## Extension Lookup

Extension lookup is performed after removing the outermost `Annotated[..., Name(...)]` wrapper, if present.

Let `base` be the resulting leaf payload.

Lookup rules:

1. If `base` is a type object and `base` is a key in `extensions`, that extension owns the leaf.
2. If `base` is not a type object and `type(base)` is a key in `extensions`, that extension owns the leaf.
3. Otherwise the built-in core rules apply.

This permits both built-in overrides and parameterized custom leaves.

Examples:

```python
bool
Annotated[bool, Name("B")]
Regex("ab|cd")
Annotated[Regex("a*"), Name("R")]
Tuple[Regex("ab|cd"), bool]
```

## Effective Constraint

Before validation, bounds inference, search, or method selection, `generate` calls:

```python
extra_i = extension_i.initialize(tree, constraint)
```

for every registered extension.

Each extension receives the original `tree` and the original `constraint`. Each call returns either `None` or one additional boolean `Expression`.

The effective constraint is:

```text
constraint_eff = And(constraint, extra_1, extra_2, ..., extra_n)
```

with all `None` results omitted.

All subsequent validation, bounds inference, search, and extension hooks use `constraint_eff`.

The order of `initialize` calls must not change the meaning of `constraint_eff`.

## Address Semantics

The `address` argument identifies the extension-owned occurrence for which a hook is being invoked.

`address` is the canonical string form of how that occurrence is referred to inside the constrained tree.

Rules:

- If the occurrence is annotated with `Name("X")`, then `address == "X"`.
- Otherwise, if the occurrence is reachable through tuple indices from an addressable parent, then `address` is the canonical dot-separated zero-based index path.
- Otherwise, `address is None`.

Examples:

- `Annotated[Regex("ab|cd"), Name("R")]` gives `address == "R"`.
- In `Annotated[Tuple[Regex("ab|cd"), bool], Name("X")]`, the regex occurrence at tuple position `0` gives `address == "X.0"`.
- In `Tuple[Regex("ab|cd"), bool]`, the regex occurrence at tuple position `0` gives `address == "0"`.
- A standalone leaf such as `Regex("ab|cd")` gives `address is None`.

If two occurrences share the same `Name` label, then they share the same `address` and denote the same logical variable.

## Domain Semantics

For an extension-owned occurrence identified by `address`, the extension methods are interpreted against the whole effective problem `(tree, constraint_eff)`.

`enumerate_all(tree, constraint_eff, address)` must yield exactly the admissible values for that address under exhaustive generation.

`arbitrary(tree, constraint_eff, address)` must return one admissible value for that address when one exists.

`uniform_random(tree, constraint_eff, address)` must return one admissible value for that address according to core `uniform_random` semantics: each satisfying assignment contributes one count to the value projected at that address.

If a hook returns `None`, that address has no admissible witness for the requested method.

## Method Semantics

Method selection is determined by labels exactly as in the core API.

- An occurrence with `Name("L")` uses `methods["L"]` when that key is present.
- If `"L"` is not present in `methods`, that occurrence uses `"all"`.
- An occurrence without `Name(...)` is not method-selectable and behaves as `"all"`.

For extension-owned occurrences:

- `"all"` uses `enumerate_all`.
- `"arbitrary"` uses `arbitrary`.
- `"uniform_random"` uses `uniform_random`.

If the same label appears in more than one occurrence, those occurrences denote one logical variable. The extension methods for that label must respect the full tree, the full effective constraint, and all occurrences of that label.

## Expression and Validation Semantics

By default, an extension-owned leaf is atomic.

For an atomic extension-owned leaf:

- equality and inequality on the whole leaf are valid,
- a non-empty address path into the leaf is invalid,
- arithmetic on the leaf is invalid,
- ordering on the leaf is invalid,
- boolean use in `And` and `Or` is invalid.

Built-in overrides preserve the built-in expression type:

- an extension registered under `bool` remains boolean-typed,
- an extension registered under `int` remains numeric-typed.

All other extension-owned leaves are opaque for expression typing.

## Finite and Infinite Domains

An extension domain may be finite or infinite.

Requirements:

- `enumerate_all` must be usable only when exhaustive generation is finite.
- If exhaustive generation would be infinite, `generate` must raise an exception.
- `uniform_random` must be usable only when the admissible support is finite and the required distribution is well-defined.
- If `uniform_random` cannot satisfy those conditions, `generate` must raise an exception.
- `arbitrary` may return a witness on an infinite admissible domain.

## Error Conditions

Generation must fail when any of the following occurs:

- `extensions` is not a mapping,
- an extension registry key is not a type,
- an extension object does not provide the required methods,
- a custom leaf appears with no matching extension,
- `initialize` returns a non-expression,
- `initialize` returns a non-boolean expression,
- an extension hook returns a value that is not admissible for its address,
- a non-empty address path is applied to an atomic extension-owned leaf,
- arithmetic or ordering is applied to an opaque extension-owned leaf,
- exhaustive generation is requested for an infinite domain,
- `uniform_random` is requested for an infinite or otherwise unsampleable admissible support.

## Worked Examples

### Built-in override: `bool`

```python
generate(bool, extensions={bool: custom_bool_extension})
```

This call uses the extension-owned boolean domain instead of the built-in `{False, True}`.

```python
generate(
    Annotated[bool, Name("B")],
    Reference("B"),
    {"B": "arbitrary"},
    extensions={bool: custom_bool_extension},
)
```

In this call, `B` remains boolean-typed and witness selection for `B` is delegated to `arbitrary(tree, constraint_eff, "B")`.

### Regex extension

```python
generate(Regex("ab|cd"), extensions={Regex: regex_extension})
```

This call returns the exhaustive finite set produced by `enumerate_all(tree, constraint_eff, None)`.

```python
generate(
    Annotated[Regex("a*"), Name("R")],
    _DEFAULT_CONSTRAINT,
    {"R": "arbitrary"},
    extensions={Regex: regex_extension},
)
```

This call delegates witness selection for `R` to `arbitrary(tree, constraint_eff, "R")`.