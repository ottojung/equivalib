# SAT Solver Specification for equivalib

## Purpose

This document specifies how a compliant implementation of equivalib MUST use a SAT/CP solver to evaluate constraints efficiently.

[docs/spec1.md](spec1.md) defines the observable semantics of the `generate` function.
[docs/caching.md](caching.md) defines caching guarantees for constraint-independent subtrees.
[docs/extensions.md](extensions.md) defines the planned extension mechanism for custom leaves and built-in overrides.
This document defines the required solver backend and the required patterns for using it.

Integrating a SAT/CP solver has the purpose of efficiently evaluating constraints.
A good implementation will achieve a super-linear speedup over an enumerative approach by leveraging the solver's internal search heuristics and domain propagation.

## Normative Terms

The words MUST, MUST NOT, SHOULD, SHOULD NOT, and MAY are to be interpreted as normative requirements.

## Solver Dependency

A compliant implementation MUST use the `ortools` library as its SAT/CP solver dependency.

Specifically, a compliant implementation MUST use the CP-SAT module:

```python
from ortools.sat.python import cp_model
```

No other solver library is permitted as the primary constraint-satisfaction backend.

## Variable Encoding

### Boolean variables

Every super label whose domain is `bool` MUST be encoded as a CP-SAT Boolean variable:

```python
var = model.NewBoolVar(label)
```

### Integer variables

Every super label whose domain is a bounded integer range `[low, high]` MUST be encoded as a CP-SAT integer variable:

```python
var = model.NewIntVar(low, high, label)
```

The bounds `low` and `high` are the inclusive minimum and maximum of the domain, as defined by `ValueRange` in the type tree.

### No other encodings

A compliant implementation MUST NOT encode super labels as unconstrained Python objects during constraint evaluation.
Encoding a label as a plain Python value and then enumerating its domain in pure Python is only permitted for non-super labels, or for guaranteed-cacheable subtrees as defined in [docs/caching.md](caching.md).

In the planned extension design from [docs/extensions.md](extensions.md), extension-owned leaves remain solver-external in the first iteration unless a later extension contract explicitly adds solver-native support.

## Constraint Encoding

A compliant implementation MUST translate every binary comparison constraint into a CP-SAT constraint before invoking the solver.

The following constraint types MUST be supported:

| Expression | CP-SAT encoding |
|---|---|
| `Eq(a, b)` | `model.Add(var_a == var_b)` |
| `Ne(a, b)` | `model.Add(var_a != var_b)` |
| `Lt(a, b)` | `model.Add(var_a < var_b)` |
| `Le(a, b)` | `model.Add(var_a <= var_b)` |
| `Gt(a, b)` | `model.Add(var_a > var_b)` |
| `Ge(a, b)` | `model.Add(var_a >= var_b)` |

As defined in [docs/spec1.md](spec1.md), `Lt`, `Le`, `Gt`, and `Ge` apply only to integers.
A compliant implementation MUST reject any use of these operators with non-integer operands at validation time rather than encoding them in CP-SAT.

### Type-aware comparison encoding

CP-SAT internally models `BoolVar` as a 0/1 integer variable, so a direct CP-SAT equality between a boolean-typed operand and an integer-typed operand could produce a wrong result — it would treat `True == 1` as satisfiable, violating the spec's requirement that `bool` and `int` are disjoint types (`True != 1`, `False != 0`).

A compliant implementation MUST apply type-aware comparison handling to all comparison operands whose declared or inferred types are known at validation/encoding time, including super labels, literals/constants, and computed arithmetic subexpressions.

- If the two operands of `Eq` or `Ne` have different declared or inferred types (one `bool`, one `int`), the implementation MUST resolve the comparison to a compile-time constant **before** encoding anything in CP-SAT:
  - `Eq(bool_expr, int_expr)` → always `False`; add `model.AddBoolOr([])` (an empty disjunction, which is always unsatisfiable) or any equivalent constant-false constraint.
  - `Ne(bool_expr, int_expr)` → always `True`; the constraint is vacuous and need not be added to the model.
- `Lt`, `Le`, `Gt`, `Ge` between a boolean-typed operand and an integer-typed operand are ill-typed per [docs/spec1.md](spec1.md) and MUST be rejected at validation time rather than encoded in CP-SAT.

When both operands have the same declared or inferred type:
- `Eq` and `Ne` MUST use the standard `model.Add(...)` encoding described above.
- `Lt`, `Le`, `Gt`, and `Ge` MUST use the standard `model.Add(...)` encoding described above only when both operands have declared type `int`.
- `Lt`, `Le`, `Gt`, and `Ge` with two `bool` operands are ill-typed per [docs/spec1.md](spec1.md) and MUST be rejected at validation time rather than encoded in CP-SAT.

### Compound boolean expressions

For compound boolean expressions (`And`, `Or`), the implementation MUST decompose them into their sub-expressions and encode each sub-expression as a separate CP-SAT constraint or a reified constraint as appropriate.

`Neg` is arithmetic negation as defined in [docs/spec1.md](spec1.md), not a boolean combinator.
When `Neg`, `Add`, `Sub`, `Mul`, `FloorDiv`, or `Mod` appears as an operand to `Eq`, `Ne`, `Lt`, `Le`, `Gt`, or `Ge`, the implementation MUST first apply the type-aware rules above.
In particular, `Eq`/`Ne` between a boolean-typed expression and an integer-typed expression MUST be constant-folded even when either side is a literal or an arithmetic subexpression.
Otherwise, the implementation MUST represent the arithmetic subexpression as a CP-SAT linear expression or as an auxiliary integer variable constrained to equal the subexpression's value, and then use that integer-valued result in the enclosing comparison constraint.

A constant reference `BooleanConstant(False)` as the top-level constraint MUST cause the solver to report unsatisfiable immediately, without encoding any variables.

## Satisfiability Check

A compliant implementation MUST check satisfiability by calling:

```python
solver = cp_model.CpSolver()
status = solver.Solve(model)
satisfiable = status in (cp_model.OPTIMAL, cp_model.FEASIBLE)
```

The implementation MUST NOT rely on any other status code to determine satisfiability.

## Model Cloning for Branching

When the implementation needs to explore multiple constraint branches (e.g., when enumerating all satisfying assignments incrementally), it MUST clone the model rather than rebuild it from scratch:

```python
model_copy = model.clone()
```

Cloning avoids redundant variable and constraint construction and is cheaper than full reconstruction.

A compliant implementation MUST NOT mutate a shared model in place across branches.
Each branch MUST receive its own copy of the model.

## Variable Index Persistence

CP-SAT variables are created by name and assigned an internal proto index at creation time.
A compliant implementation MUST persist variable indices across solver calls within the same branch.

The correct way to retrieve a variable from a cloned or re-used model is by its proto index:

```python
# For integer variables:
var = model.GetIntVarFromProtoIndex(index)

# For boolean variables:
var = model.GetBoolVarFromProtoIndex(index)
```

A compliant implementation MUST NOT re-create variables by name after cloning; doing so introduces duplicate variables with fresh indices and makes previous index references stale.

## Solution Enumeration

When the implementation needs to enumerate all satisfying assignments, it MUST use the CP-SAT solution callback mechanism rather than calling `solver.Solve` once per candidate:

```python
class SolutionCollector(cp_model.CpSolverSolutionCallback):
    def __init__(self, variables):
        super().__init__()
        self._variables = variables
        self.solutions = []

    def on_solution_callback(self):
        self.solutions.append({
            name: self.Value(var)
            for name, var in self._variables.items()
        })

collector = SolutionCollector(variables)
solver = cp_model.CpSolver()
solver.parameters.enumerate_all_solutions = True
solver.Solve(model, collector)
```

The solution callback approach collects every satisfying assignment in a single solver run, which is strictly more efficient than issuing one `Solve` call per candidate assignment.

A compliant implementation MUST enable `enumerate_all_solutions` when computing the complete satisfying-assignment set `Sat(tree, constraint)`.

## Selective Enumeration Based on Methods

A compliant implementation MUST NOT enumerate all solutions when full enumeration is unnecessary.

Full enumeration (via `enumerate_all_solutions`) is only required when at least one label (SAT *or* enum) has method `"all"` or method `"uniform_random"`:

- **`"all"`**: every satisfying assignment for that label must appear in the output; skipping any solution would be incorrect.
- **`"uniform_random"`**: the probability of selecting a value must be proportional to the number of satisfying assignments supporting it; all solutions must be counted for correct weighting.  This applies regardless of whether the `"uniform_random"` label is a SAT label or an enum label — an enum label can be supported by different numbers of SAT solutions for each of its values, and collapsing those SAT solutions to a single canonical-minimum per enum branch would give every enum value equal weight, corrupting the distribution.

When every label in the problem (both SAT labels and enum labels) has method `"arbitrary"`, full enumeration MUST NOT be performed.  Instead, the implementation MUST find the canonical-minimum satisfying assignment via sequential minimization:

1. For each SAT label in structural tree order:
   a. Clone the working model and add a `minimize(label_var)` objective.
   b. Call `solver.solve(opt_model)`.  The implementation MUST check for `OPTIMAL` status (not `FEASIBLE`) because the value MUST be the proven minimum to satisfy the canonical-order requirement of `"arbitrary"`.  `FEASIBLE` would indicate the solver was interrupted before proving optimality and the value may not be the true minimum.  If the result is not `OPTIMAL`, return no solutions.
   c. Read the optimal value; record it in the assignment.
   d. Add an equality constraint fixing the label to that value in the working model.
2. Return the single assignment.

This is correct because:
- `minimize(bool_var)` returns `0` (`False`), which is canonical-first for booleans.
- `minimize(int_var)` returns the smallest integer value, which is canonical-first for integers.
- Sequential fixing ensures each subsequent label is minimized within the set of solutions already compatible with all earlier choices, exactly mirroring the `apply_methods("arbitrary")` sequential-filter logic.

The sequential-minimization path requires at most `n_sat` solver calls per enum branch (one per SAT label), each solving an optimization problem, which is significantly faster than enumerating all `O(2^n_sat)` satisfying assignments per branch.  When there are no enum labels, the entire problem yields a single canonical-minimum assignment in at most `n_sat` solver calls.

The condition for choosing the mode is:

```python
all_labels = list(sat_labels) + enum_labels
needs_all_solutions = any(
    methods.get(label, "all") != "arbitrary"
    for label in all_labels
)
```

## Incremental Constraint Addition

The legacy adoption pattern adds one constraint at a time during dataclass field construction and re-solves after each addition.
While correct, this pattern causes `O(n)` solver invocations for a constraint with `n` comparisons.

A compliant implementation SHOULD instead:

1. Collect all constraints symbolically during field evaluation.
2. Encode all constraints into the model in a single pass.
3. Invoke the solver once.

This reduces the number of solver invocations from `O(n)` to `O(1)` per candidate, yielding significant performance improvements when constraints are large.

## Solver Parameter Tuning

A compliant implementation MAY configure `cp_model.SatParameters` to improve performance.

Recommended settings for the enumeration use case:

```python
solver.parameters.enumerate_all_solutions = True
solver.parameters.num_workers = 1  # determinism
```

Setting `num_workers = 1` ensures that the order in which the solution callback is invoked is deterministic across runs.

However, solver enumeration order MUST NOT be used as the semantic ordering for the `"arbitrary"` method.
As defined in [docs/spec1.md](spec1.md), `select_arbitrary(L, S)` MUST return the first value of `projection(L, S)` under canonical value order:

1. `None`
2. booleans (`False < True`)
3. integers in ascending numeric order
4. strings in ascending lexicographic order
5. tuples in ascending lexicographic order under this same recursive value order

The implementation MUST project the collected solver solutions onto each label, then sort the projected values by canonical order, and finally select the first (smallest) element under that order.
The solver's callback invocation order is an implementation detail and MUST NOT determine which value is selected.

A compliant implementation MUST NOT set `num_workers > 1` unless it can guarantee that the observable output ordering satisfies the determinism requirements of [docs/spec1.md](spec1.md).

## Domain Propagation Before Solving

Before invoking the solver, a compliant implementation SHOULD reduce variable domains using the constraints that are known at variable-creation time.

CP-SAT performs domain propagation automatically during solving, but explicit domain tightening at variable creation:

```python
var = model.NewIntVar(tightest_low, tightest_high, label)
```

reduces the internal search space and can speed up satisfiability checking.

When the type tree provides a bounded integer domain from `ValueRange`, those bounds MUST be used as the initial domain of the corresponding variable.

## Interaction with Caching

As described in [docs/caching.md](caching.md), subtrees that are label-closed and constraint-independent do not need a solver.
A compliant implementation MUST NOT invoke CP-SAT for such subtrees.

A compliant implementation SHOULD identify guaranteed-cacheable subtrees before building the CP-SAT model, and exclude their labels from the model entirely.
This reduces model size and solver runtime.

## Summary of Requirements

| Requirement | Level |
|---|---|
| Use `ortools.sat.python.cp_model` as solver backend | MUST |
| Encode boolean super labels as `NewBoolVar` | MUST |
| Encode bounded-integer super labels as `NewIntVar` with correct bounds | MUST |
| Translate comparison expressions to `model.Add(...)` calls | MUST |
| Apply type-aware comparison handling to all operands (labels, constants, and arithmetic subexpressions) | MUST |
| Resolve mixed bool/int `Eq`/`Ne` as compile-time constants before CP-SAT encoding | MUST |
| Reject `Lt`/`Le`/`Gt`/`Ge` with non-integer operands (bool or mixed types) at validation time | MUST |
| Check satisfiability via `CpSolver().Solve(model)` and `OPTIMAL`/`FEASIBLE` | MUST |
| Clone models for branches instead of mutating shared state | MUST |
| Persist variable proto indices across solver calls within a branch | MUST |
| Use solution callback with `enumerate_all_solutions` only when any label has method `"all"` or `"uniform_random"` | MUST |
| Use sequential minimization (not full enumeration) when all labels have method `"arbitrary"` | MUST |
| Select `"arbitrary"` witness by canonical value order, not solver callback order | MUST |
| Encode `And`/`Or` as CP-SAT constraints; encode arithmetic (`Neg`, `Add`, etc.) as linear expressions | MUST |
| Collect all constraints before solving instead of re-solving per comparison | SHOULD |
| Tune `num_workers = 1` for deterministic callback invocation | SHOULD |
| Exclude guaranteed-cacheable subtrees from the CP-SAT model | SHOULD |
| Use tightest available bounds when creating integer variables | SHOULD |
| Apply `num_workers > 1` without breaking determinism guarantees | MUST NOT |
| Rebuild variables from scratch after model cloning | MUST NOT |
| Use any solver other than `ortools` as the primary backend | MUST NOT |
| Enumerate all solutions when all labels have method `"arbitrary"` | MUST NOT |
