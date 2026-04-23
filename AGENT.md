# Agent Guide

## Project overview

`equivalib` is a Python library for systematic generation of problem instances through equivalence partitioning for algorithmic testing.
It provides a `generate` function that takes a type tree, a constraint expression, and per-label methods, and returns the set of all conforming runtime values.

## Setup

```bash
uv sync --all-extras
```

## Running tests

```bash
uv run pytest -v
```

## Type checking

```bash
uv run mypy src/equivalib tests
```

Mypy runs in **strict mode** with `warn_unused_ignores = true`.
This means:
- All code must be fully typed.
- Unnecessary `# type: ignore` comments cause errors.
- Only add `# type: ignore[error-code]` when the error is real and cannot be fixed another way.

## Linting

```bash
uv run ruff check src/ tests/
```

## Key source locations

| Path | Purpose |
|---|---|
| `src/equivalib/core/` | Core `generate` implementation (SAT, types, methods, ordering) |
| `src/equivalib/core/sat.py` | CP-SAT encoding for bool/int-range labels |
| `src/equivalib/core/types.py` | IR node types and tree helpers (`labels_in_order`, etc.) |
| `src/equivalib/core/methods.py` | `apply_methods` – witness selection per label |
| `src/equivalib/core/api.py` | Public `generate` entry point |
| `src/equivalib/sentence_model.py` | CP-SAT model wrapper (`SentenceModel`) |
| `docs/spec1.md` | Full formal specification of `generate` semantics |
| `tests/` | Pytest test suite (run before committing) |

## OR-Tools / CP-SAT API

Use **snake_case** throughout (e.g. `model.new_int_var`, `model.add`, `solver.solve`, `var.index`).
The old camelCase aliases (`NewIntVar`, `Add`, `Solve`, `var.Index()`) are deprecated and must not be used.

## Backwards compatibility

**Backwards compatibility is not a concern unless explicitly requested.**
Change public APIs freely when the new interface is cleaner, more correct, or better typed.
