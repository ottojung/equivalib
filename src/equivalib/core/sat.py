"""CP-SAT based satisfying-assignment search.

Implements the SAT specification from docs/sat.md.

Public API:
    sat_search(node, constraint) -> list[dict]

Each element in the returned list is a dict mapping label -> value,
representing one satisfying assignment.
"""

from __future__ import annotations

from typing import Any

from ortools.sat.python import cp_model

from equivalib.core.expression import (
    BooleanConstant,
    IntegerConstant,
    Reference,
    Neg,
    Add,
    Sub,
    Mul,
    FloorDiv,
    Mod,
    Eq,
    Ne,
    Lt,
    Le,
    Gt,
    Ge,
    And,
    Or,
    Expression,
    impossible,
)
from equivalib.core.types import (
    BoolNode,
    IntRangeNode,
    TupleNode,
    UnionNode,
    NamedNode,
    NoneNode,
    LiteralNode,
    IRNode,
    labels as tree_labels,
)
from equivalib.core.domains import domain_map
from equivalib.core.order import canonical_key, canonical_sorted
from equivalib.core.eval import _structural_eq, eval_expression_partial

# ---------------------------------------------------------------------------
# Kind constants
# ---------------------------------------------------------------------------
_BOOL = "bool"
_INT = "int"
_OTHER = "other"
_ZERO_DIV = "zero_div"  # sentinel: operand is undefined due to division by zero

# Encoded expression: (value, kind, is_const)
# - value: CP-SAT LinearExpr / BoolVar / IntVar, or a Python constant
# - kind: _BOOL | _INT | _OTHER
# - is_const: True iff value is a plain Python object (not a CP-SAT expression)
_EncResult = tuple[Any, str, bool]


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def sat_search(node: IRNode, constraint: Expression) -> list[dict[str, object]]:
    """Return all satisfying assignments using CP-SAT for bool/int-range labels.

    Boolean and integer-range labels are encoded as CP-SAT variables.
    All other labels (string/None/tuple literals, mixed unions) are enumerated
    in Python via backtracking, with CP-SAT invoked for the remaining labels.
    """
    domains = domain_map(node)

    # Early exit: any empty domain means no satisfying assignments.
    for domain_vals in domains.values():
        if not domain_vals:
            return []

    # Classify labels into CP-SAT-encodable (bool / int-range) and enum.
    sat_kinds, enum_label_set = _classify_labels(node)

    # Restrict to labels that actually appear in the tree.
    tree_label_set = tree_labels(node)
    sat_kinds = {lbl: knd for lbl, knd in sat_kinds.items() if lbl in tree_label_set}
    enum_labels = sorted(enum_label_set & tree_label_set)

    # Precompute canonical-sorted domain lists for enum labels.
    sorted_enum_domains: dict[str, list[object]] = {
        label: canonical_sorted(domains[label])
        for label in enum_labels
    }

    # Precompute integer bounds for CP-SAT variable creation.
    sat_bounds: dict[str, tuple[int, int]] = {}
    for label, kind in sat_kinds.items():
        if kind == _INT:
            int_vals = [v for v in domains[label] if isinstance(v, int) and not isinstance(v, bool)]
            sat_bounds[label] = (min(int_vals), max(int_vals)) if int_vals else (0, 0)
        else:  # bool
            sat_bounds[label] = (0, 1)

    results: list[dict[str, object]] = []
    _enum_backtrack(
        enum_labels,
        sorted_enum_domains,
        sat_kinds,
        sat_bounds,
        domains,
        constraint,
        {},
        results,
    )

    # Sort results in canonical label order so that downstream consumers
    # (e.g. apply_methods with uniform_random) receive a deterministic,
    # seed-reproducible sequence that matches the old backtracking order.
    sorted_labels = sorted(tree_label_set)
    results.sort(key=lambda asgn: tuple(canonical_key(asgn[lbl]) for lbl in sorted_labels))

    return results


# ---------------------------------------------------------------------------
# Label classification
# ---------------------------------------------------------------------------

def _classify_labels(node: IRNode) -> tuple[dict[str, str], set[str]]:
    """Classify labels into CP-SAT-encodable and enum categories.

    Returns:
        sat_kinds:   dict mapping label -> "bool" or "int"
        enum_labels: set of labels not suitable for direct CP-SAT encoding
    """
    kind_map: dict[str, str] = {}
    _collect_label_kinds(node, kind_map)

    sat_kinds: dict[str, str] = {}
    enum_labels: set[str] = set()
    for label, kind in kind_map.items():
        if kind in (_BOOL, _INT):
            sat_kinds[label] = kind
        else:
            enum_labels.add(label)
    return sat_kinds, enum_labels


def _collect_label_kinds(node: IRNode, out: dict[str, str]) -> None:
    """Walk the tree and record the inner-node kind for every NamedNode."""
    if isinstance(node, (NoneNode, BoolNode, LiteralNode, IntRangeNode)):
        return
    if isinstance(node, TupleNode):
        for item in node.items:
            _collect_label_kinds(item, out)
    elif isinstance(node, UnionNode):
        for opt in node.options:
            _collect_label_kinds(opt, out)
    elif isinstance(node, NamedNode):
        inner = node.inner
        if isinstance(inner, BoolNode):
            new_kind: str = _BOOL
        elif isinstance(inner, IntRangeNode):
            new_kind = _INT
        else:
            new_kind = _OTHER
        if node.label in out:
            if out[node.label] != new_kind:
                out[node.label] = _OTHER  # conflicting kinds across occurrences
        else:
            out[node.label] = new_kind
        _collect_label_kinds(inner, out)
    else:
        impossible(node)


# ---------------------------------------------------------------------------
# Enum-label backtracking
# ---------------------------------------------------------------------------

def _enum_backtrack(
    enum_label_list: list[str],
    sorted_enum_domains: dict[str, list[object]],
    sat_kinds: dict[str, str],
    sat_bounds: dict[str, tuple[int, int]],
    all_domains: dict[str, list[object]],
    constraint: Expression,
    enum_assignment: dict[str, object],
    results: list[dict[str, object]],
) -> None:
    """Iterate over enum-label combinations; for each, invoke CP-SAT."""
    if enum_label_list:
        label = enum_label_list[0]
        rest = enum_label_list[1:]
        for value in sorted_enum_domains.get(label, []):
            enum_assignment[label] = value
            # Partial-evaluation pruning: skip only if constraint is definitely
            # False under the current enum assignment. ZeroDivisionError is
            # treated as Unknown (None) rather than False because a later SAT
            # assignment may short-circuit the offending sub-expression (e.g.
            # Or(B=True, Eq(FloorDiv(X, 0), 1)) is True for any X).
            try:
                partial = eval_expression_partial(constraint, enum_assignment)
            except ZeroDivisionError:
                partial = None
            if partial is not False:
                _enum_backtrack(
                    rest, sorted_enum_domains, sat_kinds, sat_bounds,
                    all_domains, constraint, enum_assignment, results,
                )
            del enum_assignment[label]
        return

    # All enum labels are assigned.
    if not sat_kinds:
        # No CP-SAT labels: evaluate the constraint directly in Python.
        try:
            result = eval_expression_partial(constraint, enum_assignment)
        except ZeroDivisionError:
            result = False
        if result is True:
            results.append(dict(enum_assignment))
        return

    # Solve via CP-SAT for the sat labels.
    sat_solutions = _solve_sat(sat_kinds, sat_bounds, all_domains, constraint, enum_assignment)
    for sat_sol in sat_solutions:
        full = dict(enum_assignment)
        full.update(sat_sol)
        results.append(full)


# ---------------------------------------------------------------------------
# CP-SAT solver
# ---------------------------------------------------------------------------

def _solve_sat(
    sat_kinds: dict[str, str],
    sat_bounds: dict[str, tuple[int, int]],
    all_domains: dict[str, list[object]],
    constraint: Expression,
    enum_assignment: dict[str, object],
) -> list[dict[str, object]]:
    """Build and solve the CP-SAT model; return all satisfying assignments."""
    model = cp_model.CpModel()

    # Create one CP-SAT variable per sat label.
    sat_vars: dict[str, Any] = {}
    for label, kind in sat_kinds.items():
        if kind == _BOOL:
            var = model.new_bool_var(label)
            # Tighten domain if the intersection has already narrowed it.
            dom = all_domains.get(label, [])
            if dom == [True]:
                model.add_bool_and([var])
            elif dom == [False]:
                model.add_bool_and([~var])
            sat_vars[label] = var
        else:  # int
            lo, hi = sat_bounds[label]
            sat_vars[label] = model.new_int_var(lo, hi, label)

    # Encode the constraint into the model.
    counter = [0]  # mutable counter for unique auxiliary variable names
    _add_constraint(model, sat_vars, sat_kinds, enum_assignment, sat_bounds, constraint, counter)

    # Enumerate all solutions with a solution callback.
    class _SolutionCollector(cp_model.CpSolverSolutionCallback):
        def __init__(self, variables: dict[str, Any], kinds: dict[str, str]) -> None:
            super().__init__()
            self._variables = variables
            self._kinds = kinds
            self.solutions: list[dict[str, object]] = []

        def on_solution_callback(self) -> None:
            sol: dict[str, object] = {}
            for name, var in self._variables.items():
                int_val = self.value(var)
                sol[name] = bool(int_val) if self._kinds[name] == _BOOL else int_val
            self.solutions.append(sol)

    collector = _SolutionCollector(sat_vars, sat_kinds)
    solver = cp_model.CpSolver()
    solver.parameters.enumerate_all_solutions = True
    # Keep single-threaded so the solution callback is invoked sequentially,
    # which is required by the ortools callback API.
    solver.parameters.num_workers = 1
    solver.solve(model, collector)
    return collector.solutions


# ---------------------------------------------------------------------------
# Hard constraint encoding
# ---------------------------------------------------------------------------

def _add_constraint(
    model: cp_model.CpModel,
    sat_vars: dict[str, Any],
    sat_kinds: dict[str, str],
    enum_assignment: dict[str, object],
    sat_bounds: dict[str, tuple[int, int]],
    expr: Expression,
    counter: list[int],
) -> None:
    """Add ``expr`` as a hard boolean constraint to ``model``."""

    if isinstance(expr, BooleanConstant):
        if not expr.value:
            model.add_bool_or([])  # always unsatisfiable
        return  # BooleanConstant(True): no constraint needed

    if isinstance(expr, Reference):
        label = expr.label
        if label in sat_vars and sat_kinds[label] == _BOOL:
            # Boolean SAT variable used directly as a constraint (must be True).
            model.add_bool_and([sat_vars[label]])
            return
        if label in enum_assignment:
            v: object = enum_assignment[label]
            if v is False:
                model.add_bool_or([])  # constraint is False → unsatisfiable
            # v is True → no constraint needed
            return
        raise ValueError(f"Reference to unknown label {label!r} in _add_constraint")  # should not reach

    if isinstance(expr, And):
        _add_constraint(model, sat_vars, sat_kinds, enum_assignment, sat_bounds, expr.left, counter)
        _add_constraint(model, sat_vars, sat_kinds, enum_assignment, sat_bounds, expr.right, counter)
        return

    if isinstance(expr, Or):
        b_left = _reify_constraint(model, sat_vars, sat_kinds, enum_assignment, sat_bounds, expr.left, counter)
        b_right = _reify_constraint(model, sat_vars, sat_kinds, enum_assignment, sat_bounds, expr.right, counter)
        model.add_bool_or([b_left, b_right])
        return

    if isinstance(expr, (Eq, Ne, Lt, Le, Gt, Ge)):
        left = _encode_arith(model, sat_vars, sat_kinds, enum_assignment, sat_bounds, expr.left, counter)
        right = _encode_arith(model, sat_vars, sat_kinds, enum_assignment, sat_bounds, expr.right, counter)
        _add_comparison(model, left, right, _op_of(expr))
        return

    raise TypeError(f"Expected a boolean expression at top level, got {type(expr).__name__!r}: {expr!r}")


# ---------------------------------------------------------------------------
# Reified constraint encoding
# ---------------------------------------------------------------------------

def _reify_constraint(
    model: cp_model.CpModel,
    sat_vars: dict[str, Any],
    sat_kinds: dict[str, str],
    enum_assignment: dict[str, object],
    sat_bounds: dict[str, tuple[int, int]],
    expr: Expression,
    counter: list[int],
) -> Any:  # Returns a CP-SAT BoolVar
    """Return a BoolVar that is 1 iff ``expr`` is satisfied."""

    if isinstance(expr, BooleanConstant):
        counter[0] += 1
        b = model.new_bool_var(f"_c{counter[0]}")
        if expr.value:
            model.add_bool_and([b])
        else:
            model.add_bool_and([~b])
        return b

    if isinstance(expr, Reference):
        label = expr.label
        counter[0] += 1
        b = model.new_bool_var(f"_ref{counter[0]}")
        if label in sat_vars and sat_kinds[label] == _BOOL:
            # Reify the boolean SAT variable directly.
            model.add(sat_vars[label] == b)
        elif label in enum_assignment:
            v: object = enum_assignment[label]
            if v is True:
                model.add_bool_and([b])
            else:
                model.add_bool_and([~b])
        else:
            raise ValueError(f"Reference to unknown label {label!r} in _reify_constraint")  # should not reach
        return b

    if isinstance(expr, And):
        b_left = _reify_constraint(model, sat_vars, sat_kinds, enum_assignment, sat_bounds, expr.left, counter)
        b_right = _reify_constraint(model, sat_vars, sat_kinds, enum_assignment, sat_bounds, expr.right, counter)
        counter[0] += 1
        b = model.new_bool_var(f"_and{counter[0]}")
        model.add_bool_and([b_left, b_right]).only_enforce_if(b)
        model.add_bool_or([~b_left, ~b_right]).only_enforce_if(~b)
        return b

    if isinstance(expr, Or):
        b_left = _reify_constraint(model, sat_vars, sat_kinds, enum_assignment, sat_bounds, expr.left, counter)
        b_right = _reify_constraint(model, sat_vars, sat_kinds, enum_assignment, sat_bounds, expr.right, counter)
        counter[0] += 1
        b = model.new_bool_var(f"_or{counter[0]}")
        model.add_bool_or([b_left, b_right]).only_enforce_if(b)
        model.add_bool_and([~b_left, ~b_right]).only_enforce_if(~b)
        return b

    if isinstance(expr, (Eq, Ne, Lt, Le, Gt, Ge)):
        left = _encode_arith(model, sat_vars, sat_kinds, enum_assignment, sat_bounds, expr.left, counter)
        right = _encode_arith(model, sat_vars, sat_kinds, enum_assignment, sat_bounds, expr.right, counter)
        return _reify_comparison(model, left, right, _op_of(expr), counter)

    raise TypeError(f"Expected a boolean expression in reification, got {type(expr).__name__!r}: {expr!r}")


# ---------------------------------------------------------------------------
# Arithmetic expression encoding
# ---------------------------------------------------------------------------

def _encode_arith(
    model: cp_model.CpModel,
    sat_vars: dict[str, Any],
    sat_kinds: dict[str, str],
    enum_assignment: dict[str, object],
    sat_bounds: dict[str, tuple[int, int]],
    expr: Expression,
    counter: list[int],
) -> _EncResult:
    """Encode an arithmetic (or leaf) expression.

    Returns ``(value, kind, is_const)`` where:
      * ``value``    – CP-SAT LinearExpr / BoolVar / IntVar, or a Python scalar
      * ``kind``     – ``_BOOL`` | ``_INT`` | ``_OTHER``
      * ``is_const`` – True iff ``value`` is a plain Python object
    """
    if isinstance(expr, BooleanConstant):
        # Represent booleans as 0/1 integers for CP-SAT arithmetic;
        # keep kind=_BOOL so type-aware comparisons can detect the bool type.
        return (int(expr.value), _BOOL, True)

    if isinstance(expr, IntegerConstant):
        return (expr.value, _INT, True)

    if isinstance(expr, Reference):
        label = expr.label
        if label in sat_vars:
            # CP-SAT variable; references to sat labels always have empty paths.
            return (sat_vars[label], sat_kinds[label], False)
        if label in enum_assignment:
            # Navigate the path in the Python value.
            v: object = enum_assignment[label]
            for idx in expr.path:
                v = v[idx]  # type: ignore[index]
            if isinstance(v, bool):
                return (int(v), _BOOL, True)
            if isinstance(v, int):
                return (v, _INT, True)
            return (v, _OTHER, True)
        raise ValueError(f"Reference to unknown label {label!r}")  # should not reach

    if isinstance(expr, Neg):
        (val, kind, is_const) = _encode_arith(
            model, sat_vars, sat_kinds, enum_assignment, sat_bounds, expr.operand, counter
        )
        if is_const:
            assert isinstance(val, int)
            return (-val, _INT, True)
        return (-val, _INT, False)  # CP-SAT LinearExpr negation via unary minus

    if isinstance(expr, (Add, Sub)):
        (lv, _lk, lc) = _encode_arith(
            model, sat_vars, sat_kinds, enum_assignment, sat_bounds, expr.left, counter
        )
        (rv, _rk, rc) = _encode_arith(
            model, sat_vars, sat_kinds, enum_assignment, sat_bounds, expr.right, counter
        )
        if lc and rc:
            assert isinstance(lv, int) and isinstance(rv, int)
            return (lv + rv if isinstance(expr, Add) else lv - rv, _INT, True)
        return ((lv + rv) if isinstance(expr, Add) else (lv - rv), _INT, False)

    if isinstance(expr, Mul):
        (lv, _lk, lc) = _encode_arith(
            model, sat_vars, sat_kinds, enum_assignment, sat_bounds, expr.left, counter
        )
        (rv, _rk, rc) = _encode_arith(
            model, sat_vars, sat_kinds, enum_assignment, sat_bounds, expr.right, counter
        )
        if lc and rc:
            assert isinstance(lv, int) and isinstance(rv, int)
            return (lv * rv, _INT, True)
        if lc and isinstance(lv, int):
            # Scalar multiplication: constant * cp_expr
            return (rv * lv, _INT, False)
        if rc and isinstance(rv, int):
            # Scalar multiplication: cp_expr * constant
            return (lv * rv, _INT, False)
        # Both are CP-SAT variables: need auxiliary variable.
        lo, hi = _compute_bounds(expr, sat_bounds, enum_assignment)
        counter[0] += 1
        aux = model.new_int_var(lo, hi, f"_mul{counter[0]}")
        model.add_multiplication_equality(aux, [lv, rv])
        return (aux, _INT, False)

    if isinstance(expr, FloorDiv):
        (lv, _lk, lc) = _encode_arith(
            model, sat_vars, sat_kinds, enum_assignment, sat_bounds, expr.left, counter
        )
        (rv, _rk, rc) = _encode_arith(
            model, sat_vars, sat_kinds, enum_assignment, sat_bounds, expr.right, counter
        )
        if lc and rc:
            assert isinstance(lv, int) and isinstance(rv, int)
            if rv == 0:
                # Division by zero: propagate sentinel so comparisons evaluate to False.
                return (0, _ZERO_DIV, True)
            return (lv // rv, _INT, True)
        if rc and rv == 0:
            # Constant zero divisor with variable dividend: always undefined.
            return (0, _ZERO_DIV, True)
        # Encode Python floor division via Euclidean identity a = b*q + r.
        r_lo, r_hi = _compute_bounds(expr.right, sat_bounds, enum_assignment)
        q_lo, q_hi = _compute_bounds(expr, sat_bounds, enum_assignment)
        q, _r = _encode_floor_div_or_mod(
            model, lv, rv, lc, rc, r_lo, r_hi, q_lo, q_hi, counter, "fdiv",
        )
        return (q, _INT, False)

    if isinstance(expr, Mod):
        (lv, _lk, lc) = _encode_arith(
            model, sat_vars, sat_kinds, enum_assignment, sat_bounds, expr.left, counter
        )
        (rv, _rk, rc) = _encode_arith(
            model, sat_vars, sat_kinds, enum_assignment, sat_bounds, expr.right, counter
        )
        if lc and rc:
            assert isinstance(lv, int) and isinstance(rv, int)
            if rv == 0:
                # Modulo by zero: propagate sentinel so comparisons evaluate to False.
                return (0, _ZERO_DIV, True)
            return (lv % rv, _INT, True)
        if rc and rv == 0:
            # Constant zero divisor with variable dividend: always undefined.
            return (0, _ZERO_DIV, True)
        # Encode Python floor modulo via Euclidean identity a = b*q + r.
        r_lo, r_hi = _compute_bounds(expr.right, sat_bounds, enum_assignment)
        q_lo, q_hi = _compute_bounds(FloorDiv(expr.left, expr.right), sat_bounds, enum_assignment)
        _q, r = _encode_floor_div_or_mod(
            model, lv, rv, lc, rc, r_lo, r_hi, q_lo, q_hi, counter, "mod",
        )
        return (r, _INT, False)

    raise TypeError(f"Expected arithmetic expression, got {type(expr).__name__!r}: {expr!r}")


def _floor_div_remainder_bounds(div_lo: int, div_hi: int) -> tuple[int, int]:
    """Return conservative bounds on ``r`` in the Euclidean identity ``a = b*q + r``.

    For Python floor division semantics:
      - If b > 0: 0 <= r <= b - 1
      - If b < 0: b + 1 <= r <= 0
      - Mixed or unknown: -(|b|-1) <= r <= |b|-1
    Returns a symmetric conservative bound ``(-max_r, max_r)`` safe for all
    cases, suitable as the ``new_int_var`` domain when the exact sign of ``b``
    is not yet determined.
    """
    max_abs_b = max(abs(div_lo), abs(div_hi))
    if max_abs_b == 0:
        return (0, 0)
    max_r = max_abs_b - 1
    return (-max_r, max_r)


def _encode_floor_div_or_mod(
    model: cp_model.CpModel,
    lv: Any,
    rv: Any,
    lc: bool,
    rc: bool,
    r_lo: int,
    r_hi: int,
    q_lo: int,
    q_hi: int,
    counter: list[int],
    tag: str,
) -> tuple[Any, Any]:
    """Encode Python floor-division identity ``a = b*q + r`` in ``model``.

    Returns ``(q, r)`` as CP-SAT IntVars with Python remainder semantics:
      - b > 0 ⟹ 0 ≤ r < b
      - b < 0 ⟹ b < r ≤ 0

    ``lv``/``rv`` are the dividend/divisor encodings; ``lc``/``rc`` indicate
    whether they are plain Python ints.  ``r_lo``/``r_hi`` are the bounds
    on the divisor expression; ``q_lo``/``q_hi`` are bounds on the quotient.
    """
    safe_r_lo, safe_r_hi = _floor_div_remainder_bounds(r_lo, r_hi)
    counter[0] += 1
    q = model.new_int_var(q_lo, q_hi, f"_{tag}_q{counter[0]}")
    counter[0] += 1
    r = model.new_int_var(safe_r_lo, safe_r_hi, f"_{tag}_r{counter[0]}")
    if rc:
        assert isinstance(rv, int)  # mypy narrowing: rc guarantees rv is a constant int
        if rv > 0:
            model.add(r >= 0)
            model.add(r < rv)
        else:
            model.add(r > rv)
            model.add(r <= 0)
        # a = b*q + r (linear since b is a constant)
        model.add(rv * q + r == lv)
    else:
        # Variable divisor: use b*q auxiliary variable (product constraint).
        counter[0] += 1
        bq_lo = min(r_lo * q_lo, r_lo * q_hi, r_hi * q_lo, r_hi * q_hi)
        bq_hi = max(r_lo * q_lo, r_lo * q_hi, r_hi * q_lo, r_hi * q_hi)
        bq = model.new_int_var(bq_lo, bq_hi, f"_{tag}_bq{counter[0]}")
        model.add_multiplication_equality(bq, [rv, q])
        model.add(bq + r == lv)
        # Enforce Python remainder sign: r >= 0 when b > 0; r <= 0 when b < 0.
        b_pos = model.new_bool_var(f"_{tag}_bpos{counter[0]}")
        model.add(rv >= 1).only_enforce_if(b_pos)
        model.add(rv <= -1).only_enforce_if(~b_pos)
        model.add(r >= 0).only_enforce_if(b_pos)
        model.add(r < rv).only_enforce_if(b_pos)
        model.add(r <= 0).only_enforce_if(~b_pos)
        model.add(r > rv).only_enforce_if(~b_pos)
    return (q, r)


# ---------------------------------------------------------------------------
# Bounds computation for auxiliary CP-SAT variables
# ---------------------------------------------------------------------------

def _compute_bounds(
    expr: Expression,
    sat_bounds: dict[str, tuple[int, int]],
    enum_assignment: dict[str, object],
) -> tuple[int, int]:
    """Compute inclusive integer bounds for an arithmetic expression."""
    _BIG = 10 ** 9

    if isinstance(expr, IntegerConstant):
        return (expr.value, expr.value)
    if isinstance(expr, BooleanConstant):
        v = int(expr.value)
        return (v, v)
    if isinstance(expr, Reference):
        label = expr.label
        if label in sat_bounds:
            return sat_bounds[label]
        if label in enum_assignment:
            v2: object = enum_assignment[label]
            for idx in expr.path:
                v2 = v2[idx]  # type: ignore[index]
            if isinstance(v2, int):  # includes bool
                iv = int(v2)
                return (iv, iv)
        return (-_BIG, _BIG)
    if isinstance(expr, Neg):
        lo, hi = _compute_bounds(expr.operand, sat_bounds, enum_assignment)
        return (-hi, -lo)
    if isinstance(expr, Add):
        l_lo, l_hi = _compute_bounds(expr.left, sat_bounds, enum_assignment)
        r_lo, r_hi = _compute_bounds(expr.right, sat_bounds, enum_assignment)
        return (l_lo + r_lo, l_hi + r_hi)
    if isinstance(expr, Sub):
        l_lo, l_hi = _compute_bounds(expr.left, sat_bounds, enum_assignment)
        r_lo, r_hi = _compute_bounds(expr.right, sat_bounds, enum_assignment)
        return (l_lo - r_hi, l_hi - r_lo)
    if isinstance(expr, Mul):
        l_lo, l_hi = _compute_bounds(expr.left, sat_bounds, enum_assignment)
        r_lo, r_hi = _compute_bounds(expr.right, sat_bounds, enum_assignment)
        products = [l_lo * r_lo, l_lo * r_hi, l_hi * r_lo, l_hi * r_hi]
        return (min(products), max(products))
    if isinstance(expr, FloorDiv):
        l_lo, l_hi = _compute_bounds(expr.left, sat_bounds, enum_assignment)
        r_lo, r_hi = _compute_bounds(expr.right, sat_bounds, enum_assignment)
        if r_lo > 0:
            # All-positive divisors: compute all four corner quotients (floor
            # division is not monotone when the dividend is negative).
            quotients = [l_lo // r_lo, l_lo // r_hi, l_hi // r_lo, l_hi // r_hi]
            return (min(quotients), max(quotients))
        max_abs = max(abs(l_lo), abs(l_hi))
        return (-max_abs, max_abs)
    if isinstance(expr, Mod):
        r_lo, r_hi = _compute_bounds(expr.right, sat_bounds, enum_assignment)
        max_abs_divisor = max(abs(r_lo), abs(r_hi))
        if max_abs_divisor == 0:
            return (-_BIG, _BIG)
        return _floor_div_remainder_bounds(r_lo, r_hi)
    return (-_BIG, _BIG)


# ---------------------------------------------------------------------------
# Comparison helpers
# ---------------------------------------------------------------------------

def _op_of(expr: Expression) -> str:
    """Return the operator name string for a comparison expression."""
    if isinstance(expr, Eq):
        return "eq"
    if isinstance(expr, Ne):
        return "ne"
    if isinstance(expr, Lt):
        return "lt"
    if isinstance(expr, Le):
        return "le"
    if isinstance(expr, Gt):
        return "gt"
    if isinstance(expr, Ge):
        return "ge"
    raise TypeError(f"Not a comparison: {expr!r}")


def _add_comparison(
    model: cp_model.CpModel,
    left: _EncResult,
    right: _EncResult,
    op: str,
) -> None:
    """Add a comparison as a hard constraint to ``model``."""
    lv, lk, lc = left
    rv, rk, rc = right

    # Zero-division sentinel: the expression is undefined, so the comparison
    # is always False (no valid assignment can satisfy it).
    if _ZERO_DIV in (lk, rk):
        model.add_bool_or([])  # always unsatisfiable
        return

    # Type mismatch: bool vs int → Eq is always False, Ne is always True.
    if (lk == _BOOL and rk == _INT) or (lk == _INT and rk == _BOOL):
        if op == "eq":
            model.add_bool_or([])  # always unsatisfiable
        # ne: always satisfied — no constraint needed
        return

    # "other"-typed operands (strings, None, tuples, …)
    if _OTHER in (lk, rk):
        if lc and rc:
            # Both are Python values; use structural equality.
            result = _structural_cmp(lv, rv, op)
            if not result:
                model.add_bool_or([])
        elif op == "eq":
            # One is a CP-SAT variable, other is an "other"-typed Python value:
            # structural type mismatch — can never be equal.
            model.add_bool_or([])
            # ne: always satisfied
        return

    # Same kind (both bool or both int).
    if lc and rc:
        if not _const_cmp(lv, rv, op):
            model.add_bool_or([])
        return

    # At least one side is a CP-SAT expression.
    if op == "eq":
        model.add(lv == rv)
    elif op == "ne":
        model.add(lv != rv)
    elif op == "lt":
        model.add(lv < rv)
    elif op == "le":
        model.add(lv <= rv)
    elif op == "gt":
        model.add(lv > rv)
    elif op == "ge":
        model.add(lv >= rv)


def _reify_comparison(
    model: cp_model.CpModel,
    left: _EncResult,
    right: _EncResult,
    op: str,
    counter: list[int],
) -> Any:  # Returns a CP-SAT BoolVar
    """Return a BoolVar that is 1 iff the comparison holds."""
    lv, lk, lc = left
    rv, rk, rc = right

    counter[0] += 1
    b = model.new_bool_var(f"_cmp{counter[0]}")

    # Zero-division sentinel: the operand is undefined; the comparison is always False.
    if _ZERO_DIV in (lk, rk):
        model.add_bool_and([~b])
        return b

    # Type mismatch: bool vs int.
    if (lk == _BOOL and rk == _INT) or (lk == _INT and rk == _BOOL):
        if op == "eq":
            model.add_bool_and([~b])  # always False
        else:  # ne
            model.add_bool_and([b])  # always True
        return b

    # "other"-typed operands.
    if _OTHER in (lk, rk):
        if lc and rc:
            result = _structural_cmp(lv, rv, op)
        else:
            # CP-SAT var vs "other" Python value: type mismatch.
            result = (op == "ne")  # ne: True; eq: False
        if result:
            model.add_bool_and([b])
        else:
            model.add_bool_and([~b])
        return b

    # Same kind, both constants.
    if lc and rc:
        if _const_cmp(lv, rv, op):
            model.add_bool_and([b])
        else:
            model.add_bool_and([~b])
        return b

    # At least one CP-SAT expression.
    if op == "eq":
        model.add(lv == rv).only_enforce_if(b)
        model.add(lv != rv).only_enforce_if(~b)
    elif op == "ne":
        model.add(lv != rv).only_enforce_if(b)
        model.add(lv == rv).only_enforce_if(~b)
    elif op == "lt":
        model.add(lv < rv).only_enforce_if(b)
        model.add(lv >= rv).only_enforce_if(~b)
    elif op == "le":
        model.add(lv <= rv).only_enforce_if(b)
        model.add(lv > rv).only_enforce_if(~b)
    elif op == "gt":
        model.add(lv > rv).only_enforce_if(b)
        model.add(lv <= rv).only_enforce_if(~b)
    elif op == "ge":
        model.add(lv >= rv).only_enforce_if(b)
        model.add(lv < rv).only_enforce_if(~b)
    return b


# ---------------------------------------------------------------------------
# Scalar comparison helpers
# ---------------------------------------------------------------------------

def _const_cmp(lv: Any, rv: Any, op: str) -> bool:
    """Compare two same-kind constants using the given operator."""
    if op == "eq":
        return bool(lv == rv)
    if op == "ne":
        return bool(lv != rv)
    if op == "lt":
        return bool(lv < rv)
    if op == "le":
        return bool(lv <= rv)
    if op == "gt":
        return bool(lv > rv)
    if op == "ge":
        return bool(lv >= rv)
    return False


def _structural_cmp(lv: object, rv: object, op: str) -> bool:
    """Structural (type-aware) comparison for 'other'-typed values."""
    if op == "eq":
        return _structural_eq(lv, rv)
    if op == "ne":
        return not _structural_eq(lv, rv)
    # Lt/Le/Gt/Ge on 'other' types are rejected by validation; never reached.
    return False
