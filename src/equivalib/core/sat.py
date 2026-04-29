"""CP-SAT based satisfying-assignment search.

Implements the SAT specification from docs/sat.md.

Public API:
    sat_search(node, constraint, methods) -> list[dict]

Each element in the returned list is a dict mapping label -> value,
representing one satisfying assignment.
"""

from __future__ import annotations

from typing import Any, Literal, Mapping, cast

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
    ParsedExpression,
    impossible,
)
from equivalib.core.types import (
    BoolNode,
    IntRangeNode,
    UnboundedIntNode,
    ExtensionNode,
    TupleNode,
    UnionNode,
    NamedNode,
    NoneNode,
    LiteralNode,
    IRNode,
    labels as tree_labels,
    labels_in_order,
)
from equivalib.core.domains import _values_node_tagged, _untag_value
from equivalib.core.order import canonical_key, canonical_sorted
from equivalib.core.eval import _structural_eq, eval_expression_partial

# ---------------------------------------------------------------------------
# Kind constants
# ---------------------------------------------------------------------------
_BOOL = "bool"
_INT = "int"
_OTHER = "other"
_ZERO_DIV = "zero_div"  # sentinel: operand is undefined due to division by zero

# Encoded expression: (value, kind, is_const, defined)
# - value:   CP-SAT LinearExpr / BoolVar / IntVar, or a Python constant
# - kind:    _BOOL | _INT | _OTHER | _ZERO_DIV
# - is_const: True iff value is a plain Python object (not a CP-SAT expression)
# - defined: True (always defined) or a CP-SAT BoolVar that is 1 iff the
#            expression is well-defined (used for variable-divisor FloorDiv/Mod
#            to avoid polluting the model with a global rv!=0 constraint)
_EncResult = tuple[Any, str, bool, Literal[True] | cp_model.IntVar]


# ---------------------------------------------------------------------------
# Tuple path addressing helper
# ---------------------------------------------------------------------------

def _follow_reference_path(value: object, path: tuple[int, ...], label: str) -> object:
    """Follow ``path`` into ``value`` using strict zero-based tuple indexing."""
    current = value
    for depth, idx in enumerate(path):
        if not isinstance(current, tuple):
            raise TypeError(
                f"Reference {label!r} path {path!r} descends into non-tuple "
                f"at depth {depth}: {current!r}."
            )
        if idx < 0 or idx >= len(current):
            raise IndexError(
                f"Reference {label!r} path {path!r} uses out-of-range zero-based "
                f"index {idx} at depth {depth} for tuple length {len(current)}."
            )
        current = current[idx]
    return current


# ---------------------------------------------------------------------------
# Domain computation helpers
# ---------------------------------------------------------------------------

def _sat_compute_domains(
    node: IRNode,
    int_sat_labels: set[str],
) -> tuple[dict[str, tuple[int, int]], dict[str, list[object]]]:
    """Compute bounds for int SAT labels and full domains for all other labels.

    For integer-range SAT labels (``IntRangeNode``), only the tightest bounds
    across all occurrences are extracted from the tree — no full value
    enumeration.  For all other labels (bool, enum), the complete domain list
    is returned via tagged-frozenset intersection (same semantics as
    ``domain_map``).

    Returns:
        int_bounds:    ``{label: (lo, hi)}`` for every label in
                       ``int_sat_labels``.  An empty intersection (``lo > hi``)
                       signals an empty domain without listing any values.
        other_domains: ``{label: [values]}`` for non-int-SAT labels.
    """
    int_occurrences: dict[str, list[tuple[int, int]]] = {}
    other_occurrences: dict[str, list[frozenset[object]]] = {}

    def _walk(n: IRNode) -> None:
        if isinstance(n, (NoneNode, BoolNode, LiteralNode, IntRangeNode, UnboundedIntNode, ExtensionNode)):
            return
        if isinstance(n, TupleNode):
            for item in n.items:
                _walk(item)
        elif isinstance(n, UnionNode):
            for opt in n.options:
                _walk(opt)
        elif isinstance(n, NamedNode):
            label = n.label
            if label in int_sat_labels and isinstance(n.inner, IntRangeNode):
                # Direct bounds extraction: no range enumeration.
                lo, hi = n.inner.min_value, n.inner.max_value
                if label not in int_occurrences:
                    int_occurrences[label] = []
                int_occurrences[label].append((lo, hi))
            else:
                tagged_vals = _values_node_tagged(n.inner)
                if label not in other_occurrences:
                    other_occurrences[label] = []
                other_occurrences[label].append(tagged_vals)
            _walk(n.inner)
        else:
            impossible(n)

    _walk(node)

    # Intersect bounds for int labels (largest lo, smallest hi across occurrences).
    int_bounds: dict[str, tuple[int, int]] = {}
    for label, bounds_list in int_occurrences.items():
        lo = max(b[0] for b in bounds_list)
        hi = min(b[1] for b in bounds_list)
        int_bounds[label] = (lo, hi)

    # Intersect tagged frozensets for other labels.
    other_domains: dict[str, list[object]] = {}
    for label, occ_list in other_occurrences.items():
        tagged_domain: frozenset[object] = occ_list[0]
        for occ in occ_list[1:]:
            tagged_domain = tagged_domain & occ
        other_domains[label] = [_untag_value(tv) for tv in tagged_domain]

    return int_bounds, other_domains


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def sat_search(
    node: IRNode,
    constraint: ParsedExpression,
    methods: Mapping[str, str] | None = None,
) -> list[dict[str, object]]:
    """Return satisfying assignments using CP-SAT for bool/int-range labels.

    When ``methods`` indicates that every label (SAT and enum alike)
    uses ``"arbitrary"``, SAT solution enumeration per enum branch is
    replaced by sequential minimization (one solver call per SAT label)
    instead of enumerating all CP-SAT solutions.  Full enumeration is
    performed when any label — SAT or enum — has method ``"all"`` or
    ``"uniform_random"``.

    Boolean and integer-range labels are encoded as CP-SAT variables.
    All other labels (string/None/tuple literals, mixed unions) are enumerated
    in Python via backtracking, with CP-SAT invoked for the remaining labels.
    """
    if methods is None:
        methods = {}
    # Classify labels into CP-SAT-encodable (bool / int-range) and enum.
    # (Done first so we know which labels are int SAT before computing domains.)
    sat_kinds, enum_label_set = _classify_labels(node)

    # Restrict to labels that actually appear in the tree.
    tree_label_set = tree_labels(node)
    sat_kinds = {lbl: knd for lbl, knd in sat_kinds.items() if lbl in tree_label_set}
    enum_labels = sorted(enum_label_set & tree_label_set)

    # Compute domains without enumerating int-range SAT labels.
    # For int SAT labels: direct (lo, hi) bounds from IntRangeNode (no range materialisation).
    # For enum and bool labels: full tagged-frozenset intersection (same as domain_map).
    int_sat_labels = {lbl for lbl, knd in sat_kinds.items() if knd == _INT}
    int_bounds, other_domains = _sat_compute_domains(node, int_sat_labels)

    # Early exit: empty domain for any label → no satisfying assignments.
    for label, (lo, hi) in int_bounds.items():
        if lo > hi:
            return []
    for domain_vals in other_domains.values():
        if not domain_vals:
            return []

    # Precompute canonical-sorted domain lists for enum labels.
    sorted_enum_domains: dict[str, list[object]] = {
        label: canonical_sorted(other_domains.get(label, []))
        for label in enum_labels
    }

    # Precompute integer bounds for CP-SAT variable creation.
    sat_bounds: dict[str, tuple[int, int]] = {}
    for label, kind in sat_kinds.items():
        if kind == _INT:
            sat_bounds[label] = int_bounds.get(label, (0, 0))
        else:  # bool
            sat_bounds[label] = (0, 1)

    results: list[dict[str, object]] = []

    # Determine whether full enumeration is needed.
    # Full enumeration is required when any label (SAT *or* enum) has method
    # "all" (the default) or "uniform_random".
    #
    # For "all": every satisfying assignment must appear in the output.
    #
    # For "uniform_random": the probability of selecting a value must be
    # proportional to the number of satisfying assignments supporting it.
    # This multiplicity comes from the full SAT enumeration — even if the
    # "uniform_random" label is an enum label, each enum value may be
    # supported by a *different* number of SAT solutions, so collapsing SAT
    # solutions to a single canonical-minimum assignment per enum branch would
    # give each enum value equal weight regardless of how many SAT solutions
    # support it, corrupting the distribution.
    #
    # Only when every label across the whole problem uses "arbitrary" can we
    # safely skip full enumeration and use sequential minimization instead.
    all_labels = list(sat_kinds) + enum_labels
    needs_all_solutions: bool = any(
        methods.get(label, "all") != "arbitrary"
        for label in all_labels
    )

    # Compute SAT labels in structural (first-DFS-appearance) order so that
    # sequential minimization follows the same order as apply_methods.
    all_labels_ordered = labels_in_order(node)
    sat_labels_in_order = [lbl for lbl in all_labels_ordered if lbl in sat_kinds]

    if sat_kinds:
        # Build the base CP-SAT model once (SAT variables + domain-tightening
        # constraints for bool labels with narrowed domains).  Each enum
        # combination will clone this base model and add the full constraint
        # encoding on the clone, avoiding redundant variable construction per
        # enum branch.
        base_model, sat_var_indices = _build_base_model(sat_kinds, sat_bounds, other_domains)
    else:
        base_model = None
        sat_var_indices = {}

    _enum_backtrack(
        enum_labels,
        sorted_enum_domains,
        sat_kinds,
        sat_bounds,
        other_domains,
        constraint,
        {},
        results,
        base_model,
        sat_var_indices,
        needs_all_solutions,
        sat_labels_in_order,
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
    if isinstance(node, (NoneNode, BoolNode, LiteralNode, IntRangeNode, UnboundedIntNode, ExtensionNode)):
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
    constraint: ParsedExpression,
    enum_assignment: dict[str, object],
    results: list[dict[str, object]],
    base_model: cp_model.CpModel | None,
    sat_var_indices: dict[str, tuple[str, int]],
    needs_all_solutions: bool,
    sat_labels_in_order: list[str],
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
                partial = eval_expression_partial(constraint, cast(dict[str | None, object], enum_assignment))
            except ZeroDivisionError:
                partial = None
            if partial is not False:
                _enum_backtrack(
                    rest, sorted_enum_domains, sat_kinds, sat_bounds,
                    all_domains, constraint, enum_assignment, results,
                    base_model, sat_var_indices,
                    needs_all_solutions, sat_labels_in_order,
                )
            del enum_assignment[label]
        return

    # All enum labels are assigned.
    if not sat_kinds:
        # No CP-SAT labels: evaluate the constraint directly in Python.
        try:
            result = eval_expression_partial(constraint, cast(dict[str | None, object], enum_assignment))
        except ZeroDivisionError:
            result = False
        if result is True:
            results.append(dict(enum_assignment))
        return

    # Solve via CP-SAT for the sat labels.
    assert base_model is not None
    sat_solutions = _solve_sat(sat_kinds, sat_bounds, all_domains, constraint, enum_assignment, base_model, sat_var_indices, needs_all_solutions, sat_labels_in_order)
    for sat_sol in sat_solutions:
        full = dict(enum_assignment)
        full.update(sat_sol)
        results.append(full)


# ---------------------------------------------------------------------------
# CP-SAT base-model builder and solver
# ---------------------------------------------------------------------------

def _build_base_model(
    sat_kinds: dict[str, str],
    sat_bounds: dict[str, tuple[int, int]],
    all_domains: dict[str, list[object]],
) -> tuple[cp_model.CpModel, dict[str, tuple[str, int]]]:
    """Create a CP-SAT model with one variable per SAT label.

    Returns ``(base_model, sat_var_indices)`` where ``sat_var_indices`` maps
    each label to ``(kind, proto_index)``.  The base model contains the SAT
    variables and any domain-tightening constraints for boolean labels whose
    intersection has narrowed the domain to a single value.

    Per docs/sat.md, this model is cloned once per enum-label combination in
    ``_solve_sat`` so that variable construction overhead is paid only once.
    """
    model: cp_model.CpModel = cp_model.CpModel()
    sat_var_indices: dict[str, tuple[str, int]] = {}
    for label, kind in sat_kinds.items():
        if kind == _BOOL:
            var = model.new_bool_var(label)
            dom = all_domains.get(label, [])
            if dom == [True]:
                model.add_bool_and([var])
            elif dom == [False]:
                model.add_bool_and([~var])
            sat_var_indices[label] = (_BOOL, var.index)
        else:  # int
            lo, hi = sat_bounds[label]
            var = model.new_int_var(lo, hi, label)
            sat_var_indices[label] = (_INT, var.index)
    return model, sat_var_indices


def _solve_sat(
    sat_kinds: dict[str, str],
    sat_bounds: dict[str, tuple[int, int]],
    all_domains: dict[str, list[object]],
    constraint: ParsedExpression,
    enum_assignment: dict[str, object],
    base_model: cp_model.CpModel,
    sat_var_indices: dict[str, tuple[str, int]],
    needs_all_solutions: bool,
    sat_labels_in_order: list[str],
) -> list[dict[str, object]]:
    """Clone the base model, add constraints, and find satisfying solutions.

    When ``needs_all_solutions`` is True (any label — SAT or enum — has
    method ``"all"`` or ``"uniform_random"``), all solutions are enumerated
    via a solution callback as per docs/sat.md.

    When ``needs_all_solutions`` is False (every label across the whole
    problem has method ``"arbitrary"``), the canonical-minimum satisfying
    assignment is found via sequential minimization: SAT labels are processed
    in structural order, each is minimized and then fixed before moving to
    the next.  This avoids full enumeration while producing the same result
    as enumerating all solutions and applying ``apply_methods`` with
    all-``"arbitrary"`` methods.

    Cloning per docs/sat.md: the base model (SAT variables + domain-tightening
    constraints) is cloned so that variable construction happens only once per
    call to ``sat_search``, not once per enum-label combination.
    """
    model: cp_model.CpModel = base_model.clone()

    # Rehydrate sat variable references from proto indices in the cloned model.
    sat_vars: dict[str, cp_model.IntVar] = {}
    for label, (kind, idx) in sat_var_indices.items():
        if kind == _BOOL:
            sat_vars[label] = model.get_bool_var_from_proto_index(idx)
        else:
            sat_vars[label] = model.get_int_var_from_proto_index(idx)

    # Encode the constraint into the cloned model.
    counter = [0]  # mutable counter for unique auxiliary variable names
    _add_constraint(model, sat_vars, sat_kinds, enum_assignment, sat_bounds, constraint, counter)

    if needs_all_solutions:
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
    else:
        # Sequential minimization: find the canonical-minimum satisfying
        # assignment without full enumeration.
        #
        # For each SAT label in structural order:
        #   1. Clone the working model and set a minimize objective on that label.
        #   2. Solve to find the optimal (smallest) value for that label.
        #   3. Fix the label to that value in the working model.
        #
        # This is correct because:
        #   - minimize(bool_var) returns 0 (False), which is canonical-first.
        #   - minimize(int_var) returns the minimum integer, which is
        #     canonical-first for integers.
        #   - Sequential fixing ensures later labels are minimized within the
        #     set of solutions already compatible with all previous choices,
        #     mirroring the apply_methods("arbitrary") sequential-filter logic.
        assignment: dict[str, object] = {}
        for label in sat_labels_in_order:
            var = sat_vars[label]
            # Clone the working model and add a minimize objective.
            opt_model = model.clone()
            _, idx = sat_var_indices[label]
            kind = sat_kinds[label]
            opt_var: cp_model.IntVar = (
                opt_model.get_bool_var_from_proto_index(idx)
                if kind == _BOOL
                else opt_model.get_int_var_from_proto_index(idx)
            )
            opt_model.minimize(opt_var)
            solver = cp_model.CpSolver()
            # Single-threaded for determinism: same requirement as enumeration.
            solver.parameters.num_workers = 1
            status = solver.solve(opt_model)
            # For a minimization problem with no time/memory limits, CP-SAT
            # returns OPTIMAL when the minimum is proven (the only success
            # status without resource constraints).  FEASIBLE would mean
            # optimality was not proven (i.e. the solver was interrupted), in
            # which case the value may not be the true minimum and accepting it
            # could violate the canonical-order requirement of "arbitrary".
            if status != cp_model.OPTIMAL:
                return []
            optimal_val = solver.value(opt_var)
            if kind == _BOOL:
                assignment[label] = bool(optimal_val)
            else:
                assignment[label] = optimal_val
            # Fix this label's value in the working model for subsequent labels.
            model.add(var == optimal_val)
        return [assignment]


# ---------------------------------------------------------------------------
# Hard constraint encoding
# ---------------------------------------------------------------------------

def _add_constraint(
    model: cp_model.CpModel,
    sat_vars: dict[str, cp_model.IntVar],
    sat_kinds: dict[str, str],
    enum_assignment: dict[str, object],
    sat_bounds: dict[str, tuple[int, int]],
    expr: ParsedExpression,
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
            v = _follow_reference_path(enum_assignment[label], tuple(expr.path), label)
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
    sat_vars: dict[str, cp_model.IntVar],
    sat_kinds: dict[str, str],
    enum_assignment: dict[str, object],
    sat_bounds: dict[str, tuple[int, int]],
    expr: ParsedExpression,
    counter: list[int],
) -> cp_model.IntVar:
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
            v = _follow_reference_path(enum_assignment[label], tuple(expr.path), label)
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

def _and_defined(model: cp_model.CpModel, d1: Literal[True] | cp_model.IntVar, d2: Literal[True] | cp_model.IntVar, counter: list[int]) -> Literal[True] | cp_model.IntVar:
    """Return a condition (True or BoolVar) representing ``d1 AND d2``.

    Used to propagate the ``defined`` status through compound arithmetic:
    if either operand of an Add/Sub/Neg/Mul is potentially undefined (i.e.
    it has a CP-SAT BoolVar as its ``defined`` field), the compound result
    is also potentially undefined under the same condition.
    """
    if d1 is True:
        return d2
    if d2 is True:
        return d1
    # Both are BoolVars: create a BoolVar that is true iff both d1 and d2 are true.
    counter[0] += 1
    b = model.new_bool_var(f"_def{counter[0]}")
    # b ⟺ (d1 AND d2): enforce both directions.
    model.add_bool_and([d1, d2]).only_enforce_if(b)   # b => d1 AND d2
    model.add_bool_or([~d1, ~d2, b])                  # d1 AND d2 => b
    return b


def _encode_arith(
    model: cp_model.CpModel,
    sat_vars: dict[str, cp_model.IntVar],
    sat_kinds: dict[str, str],
    enum_assignment: dict[str, object],
    sat_bounds: dict[str, tuple[int, int]],
    expr: ParsedExpression,
    counter: list[int],
) -> _EncResult:
    """Encode an arithmetic (or leaf) expression.

    Returns ``(value, kind, is_const, defined)`` where:
      * ``value``    – CP-SAT LinearExpr / BoolVar / IntVar, or a Python scalar
      * ``kind``     – ``_BOOL`` | ``_INT`` | ``_OTHER`` | ``_ZERO_DIV``
      * ``is_const`` – True iff ``value`` is a plain Python object
      * ``defined``  – True (always defined) or a CP-SAT BoolVar that is 1 iff
                       the expression is well-defined (non-zero divisor)
    """
    if isinstance(expr, BooleanConstant):
        # Represent booleans as 0/1 integers for CP-SAT arithmetic;
        # keep kind=_BOOL so type-aware comparisons can detect the bool type.
        return (int(expr.value), _BOOL, True, True)

    if isinstance(expr, IntegerConstant):
        return (expr.value, _INT, True, True)

    if isinstance(expr, Reference):
        label = expr.label
        if label in sat_vars:
            # CP-SAT variable; references to sat labels always have empty paths.
            return (sat_vars[label], sat_kinds[label], False, True)
        if label in enum_assignment:
            # Navigate the path in the Python value.
            v = _follow_reference_path(enum_assignment[label], tuple(expr.path), label)
            if isinstance(v, bool):
                return (int(v), _BOOL, True, True)
            if isinstance(v, int):
                return (v, _INT, True, True)
            return (v, _OTHER, True, True)
        raise ValueError(f"Reference to unknown label {label!r}")  # should not reach

    if isinstance(expr, Neg):
        (val, kind, is_const, defined) = _encode_arith(
            model, sat_vars, sat_kinds, enum_assignment, sat_bounds, expr.operand, counter
        )
        if kind == _ZERO_DIV:
            return (0, _ZERO_DIV, True, True)  # propagate undefined sentinel
        if is_const:
            assert isinstance(val, int)
            return (-val, _INT, True, True)
        return (-val, _INT, False, defined)  # CP-SAT LinearExpr negation via unary minus

    if isinstance(expr, (Add, Sub)):
        (lv, _lk, lc, ld) = _encode_arith(
            model, sat_vars, sat_kinds, enum_assignment, sat_bounds, expr.left, counter
        )
        (rv, _rk, rc, rd) = _encode_arith(
            model, sat_vars, sat_kinds, enum_assignment, sat_bounds, expr.right, counter
        )
        if _ZERO_DIV in (_lk, _rk):
            return (0, _ZERO_DIV, True, True)  # propagate undefined sentinel
        if lc and rc:
            assert isinstance(lv, int) and isinstance(rv, int)
            return (lv + rv if isinstance(expr, Add) else lv - rv, _INT, True, True)
        dd = _and_defined(model, ld, rd, counter)
        return ((lv + rv) if isinstance(expr, Add) else (lv - rv), _INT, False, dd)

    if isinstance(expr, Mul):
        (lv, _lk, lc, ld) = _encode_arith(
            model, sat_vars, sat_kinds, enum_assignment, sat_bounds, expr.left, counter
        )
        (rv, _rk, rc, rd) = _encode_arith(
            model, sat_vars, sat_kinds, enum_assignment, sat_bounds, expr.right, counter
        )
        if _ZERO_DIV in (_lk, _rk):
            return (0, _ZERO_DIV, True, True)  # propagate undefined sentinel
        if lc and rc:
            assert isinstance(lv, int) and isinstance(rv, int)
            return (lv * rv, _INT, True, True)
        if lc and isinstance(lv, int):
            # Scalar multiplication: constant * cp_expr
            return (rv * lv, _INT, False, rd)
        if rc and isinstance(rv, int):
            # Scalar multiplication: cp_expr * constant
            return (lv * rv, _INT, False, ld)
        # Both are CP-SAT variables: need auxiliary variable.
        lo, hi = _compute_bounds(expr, sat_bounds, enum_assignment)
        counter[0] += 1
        aux = model.new_int_var(lo, hi, f"_mul{counter[0]}")
        model.add_multiplication_equality(aux, [lv, rv])
        dd = _and_defined(model, ld, rd, counter)
        return (aux, _INT, False, dd)

    if isinstance(expr, FloorDiv):
        (lv, _lk, lc, ld) = _encode_arith(
            model, sat_vars, sat_kinds, enum_assignment, sat_bounds, expr.left, counter
        )
        (rv, _rk, rc, rd) = _encode_arith(
            model, sat_vars, sat_kinds, enum_assignment, sat_bounds, expr.right, counter
        )
        if _ZERO_DIV in (_lk, _rk):
            return (0, _ZERO_DIV, True, True)  # propagate undefined sentinel
        if lc and rc:
            assert isinstance(lv, int) and isinstance(rv, int)
            if rv == 0:
                # Division by zero: propagate sentinel so comparisons evaluate to False.
                return (0, _ZERO_DIV, True, True)
            return (lv // rv, _INT, True, True)
        if rc and rv == 0:
            # Constant zero divisor with variable dividend: always undefined.
            return (0, _ZERO_DIV, True, True)
        # Encode Python floor division via Euclidean identity a = b*q + r.
        r_lo, r_hi = _compute_bounds(expr.right, sat_bounds, enum_assignment)
        q_lo, q_hi = _compute_bounds(expr, sat_bounds, enum_assignment)
        q, _r, div_defined = _encode_floor_div_or_mod(
            model, lv, rv, lc, rc, r_lo, r_hi, q_lo, q_hi, counter, "fdiv",
        )
        # Propagate: defined iff both operands are defined AND divisor is non-zero.
        dd = _and_defined(model, _and_defined(model, ld, rd, counter), div_defined, counter)
        return (q, _INT, False, dd)

    if isinstance(expr, Mod):
        (lv, _lk, lc, ld) = _encode_arith(
            model, sat_vars, sat_kinds, enum_assignment, sat_bounds, expr.left, counter
        )
        (rv, _rk, rc, rd) = _encode_arith(
            model, sat_vars, sat_kinds, enum_assignment, sat_bounds, expr.right, counter
        )
        if _ZERO_DIV in (_lk, _rk):
            return (0, _ZERO_DIV, True, True)  # propagate undefined sentinel
        if lc and rc:
            assert isinstance(lv, int) and isinstance(rv, int)
            if rv == 0:
                # Modulo by zero: propagate sentinel so comparisons evaluate to False.
                return (0, _ZERO_DIV, True, True)
            return (lv % rv, _INT, True, True)
        if rc and rv == 0:
            # Constant zero divisor with variable dividend: always undefined.
            return (0, _ZERO_DIV, True, True)
        # Encode Python floor modulo via Euclidean identity a = b*q + r.
        r_lo, r_hi = _compute_bounds(expr.right, sat_bounds, enum_assignment)
        q_lo, q_hi = _compute_bounds(FloorDiv(expr.left, expr.right), sat_bounds, enum_assignment)
        _q, r, div_defined = _encode_floor_div_or_mod(
            model, lv, rv, lc, rc, r_lo, r_hi, q_lo, q_hi, counter, "mod",
        )
        dd = _and_defined(model, _and_defined(model, ld, rd, counter), div_defined, counter)
        return (r, _INT, False, dd)

    if isinstance(expr, (Eq, Ne, Lt, Le, Gt, Ge, And, Or)):
        # Boolean expression used as an arithmetic operand (e.g. Eq(Eq(X,1), True)).
        # Reify the boolean expression into a BoolVar and return it as _BOOL kind.
        bvar = _reify_constraint(model, sat_vars, sat_kinds, enum_assignment, sat_bounds, expr, counter)
        return (bvar, _BOOL, False, True)

    raise TypeError(f"Expected arithmetic expression, got {type(expr).__name__!r}: {expr!r}")


def _floor_div_remainder_bounds(div_lo: int, div_hi: int) -> tuple[int, int]:
    """Return conservative bounds on ``r`` in the Euclidean identity ``a = b*q + r``.

    For Python floor division semantics:
      - If b > 0: 0 <= r <= b - 1
      - If b < 0: b + 1 <= r <= 0
      - Mixed or unknown: -(|b|-1) <= r <= |b|-1
    Returns a symmetric conservative bound ``(-max_r, max_r)`` safe for all
    cases, suitable as the ``NewIntVar`` domain when the exact sign of ``b``
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
) -> tuple[cp_model.IntVar, cp_model.IntVar, Literal[True] | cp_model.IntVar]:
    """Encode Python floor-division identity ``a = b*q + r`` in ``model``.

    Returns ``(q, r, div_defined)`` where ``q`` and ``r`` are CP-SAT IntVars
    with Python remainder semantics:
      - b > 0 ⟹ 0 ≤ r < b
      - b < 0 ⟹ b < r ≤ 0
    and ``div_defined`` is:
      - ``True`` when the divisor is known to be non-zero (constant or domain
        that excludes 0), so the Euclidean identity is always enforced; or
      - a CP-SAT BoolVar that is 1 iff the divisor is non-zero, in which case
        the Euclidean identity and sign constraints are only enforced when that
        BoolVar is 1.  This prevents a global ``rv != 0`` constraint from being
        added when the expression appears inside an ``Or`` branch that may be
        satisfied by the other side (short-circuit semantics).

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
        # Constant non-zero divisor: always well-defined (zero was caught earlier).
        return (q, r, True)
    else:
        # Variable divisor.  If 0 is not in the divisor's domain the encoding
        # can be unconditional; otherwise we must make the Euclidean identity
        # and sign constraints conditional on a ``div_defined`` BoolVar so that
        # rv == 0 is not globally forbidden (it may be short-circuited in Or).
        counter[0] += 1
        bq_lo = min(r_lo * q_lo, r_lo * q_hi, r_hi * q_lo, r_hi * q_hi)
        bq_hi = max(r_lo * q_lo, r_lo * q_hi, r_hi * q_lo, r_hi * q_hi)
        bq = model.new_int_var(bq_lo, bq_hi, f"_{tag}_bq{counter[0]}")
        # bq = rv * q unconditionally; when rv=0 this forces bq=0 for any q.
        model.add_multiplication_equality(bq, [rv, q])

        divisor_domain_includes_zero = r_lo <= 0 <= r_hi
        if not divisor_domain_includes_zero:
            # Zero is outside the divisor's domain: use simple unconditional encoding.
            model.add(bq + r == lv)
            counter[0] += 1
            b_pos = model.new_bool_var(f"_{tag}_bpos{counter[0]}")
            model.add(rv >= 1).only_enforce_if(b_pos)
            model.add(rv <= -1).only_enforce_if(~b_pos)
            model.add(r >= 0).only_enforce_if(b_pos)
            model.add(r < rv).only_enforce_if(b_pos)
            model.add(r <= 0).only_enforce_if(~b_pos)
            model.add(r > rv).only_enforce_if(~b_pos)
            return (q, r, True)  # always defined since 0 is not in domain

        # Zero is in the divisor's domain: introduce a ``div_defined`` BoolVar
        # and make all arithmetic constraints conditional on it.
        counter[0] += 1
        div_defined = model.new_bool_var(f"_{tag}_defined{counter[0]}")
        counter[0] += 1
        b_pos = model.new_bool_var(f"_{tag}_bpos{counter[0]}")
        counter[0] += 1
        b_neg = model.new_bool_var(f"_{tag}_bneg{counter[0]}")

        # b_pos + b_neg == div_defined requires their integer sum to equal div_defined:
        #   div_defined=1 requires b_pos + b_neg = 1 (exactly one is true)
        #   div_defined=0 requires b_pos + b_neg = 0 (both are false)
        model.add(b_pos + b_neg == div_defined)

        # Sign constraints (only active when the corresponding flag is set).
        model.add(rv >= 1).only_enforce_if(b_pos)
        model.add(rv <= -1).only_enforce_if(b_neg)
        # When div_defined=False: rv must be 0.
        model.add(rv == 0).only_enforce_if(~div_defined)

        # Euclidean identity: only enforced when div_defined (avoids unnecessary
        # constraints that would make rv=0 assignments infeasible).
        model.add(bq + r == lv).only_enforce_if(div_defined)

        # Remainder sign: r >= 0 when b > 0; r <= 0 when b < 0.
        model.add(r >= 0).only_enforce_if(b_pos)
        model.add(r < rv).only_enforce_if(b_pos)
        model.add(r <= 0).only_enforce_if(b_neg)
        model.add(r > rv).only_enforce_if(b_neg)

        # Pin auxiliary variables to a fixed state when div_defined=False.
        # This prevents CP-SAT from enumerating multiple (q, r) combinations for
        # the same label assignment when the divisor is zero (which would cause
        # duplicate entries in sat_search results and bias uniform_random sampling).
        model.add(q == 0).only_enforce_if(~div_defined)
        model.add(r == 0).only_enforce_if(~div_defined)

        return (q, r, div_defined)


# ---------------------------------------------------------------------------
# Bounds computation for auxiliary CP-SAT variables
# ---------------------------------------------------------------------------

def _compute_bounds(
    expr: ParsedExpression,
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
            v2 = _follow_reference_path(enum_assignment[label], tuple(expr.path), label)
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
            # Divisor range is entirely positive (r_lo > 0): compute all four
            # corner quotients because floor division is not monotone when the
            # dividend can be negative.
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

def _op_of(expr: ParsedExpression) -> str:
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
    lv, lk, lc, ld = left
    rv, rk, rc, rd = right

    # For a hard constraint, the expression must be well-defined.
    # If either operand may be undefined (has a BoolVar ``defined``), require it.
    if ld is not True:
        model.add_bool_and([ld])
    if rd is not True:
        model.add_bool_and([rd])

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
) -> cp_model.IntVar:
    """Return a BoolVar that is 1 iff the comparison holds.

    The ``defined`` field of each operand is respected: if either operand is
    potentially undefined (has a CP-SAT BoolVar as its ``defined`` field), the
    returned BoolVar is forced to False whenever the operand is not defined.
    This avoids polluting the model with a global ``rv != 0`` constraint that
    would otherwise make ``rv=0`` assignments infeasible even when the
    comparison is short-circuited by the other branch of an ``Or``.
    """
    lv, lk, lc, ld = left
    rv, rk, rc, rd = right

    counter[0] += 1
    b = model.new_bool_var(f"_cmp{counter[0]}")

    # Zero-division sentinel: the operand is undefined; the comparison is always False.
    if _ZERO_DIV in (lk, rk):
        model.add_bool_and([~b])
        return b

    # Two-phase defined-condition handling:
    # Phase 1: Build not_b_and_defined — the list of literals for the
    #          "~b ⟹ ~comparison" constraints so they only fire when the
    #          operands are actually well-defined.
    # Phase 2: For each non-trivial defined condition, add b ⟹ defined so
    #          the comparison BoolVar cannot be True when an operand is undefined.
    not_b_and_defined: list[Any] = [~b]
    if ld is not True:
        not_b_and_defined.append(ld)
        model.add_bool_and([ld]).only_enforce_if(b)  # b ⟹ ld
    if rd is not True:
        not_b_and_defined.append(rd)
        model.add_bool_and([rd]).only_enforce_if(b)  # b ⟹ rd

    # Type mismatch: bool vs int.
    if (lk == _BOOL and rk == _INT) or (lk == _INT and rk == _BOOL):
        if op == "eq":
            model.add_bool_and([~b])  # always False (undefined ⇒ False too)
        else:  # ne
            # True only when both operands are defined; an undefined operand
            # (e.g. FloorDiv with a zero-able variable divisor) must yield False
            # so that short-circuiting under Or works correctly.
            defs = [x for x in (ld, rd) if x is not True]
            if defs:
                model.add_bool_and([b]).only_enforce_if(defs)
                model.add_bool_and([~b]).only_enforce_if([~d for d in defs])
            else:
                model.add_bool_and([b])  # both operands always defined
        return b

    # "other"-typed operands.
    if _OTHER in (lk, rk):
        if lc and rc:
            result = _structural_cmp(lv, rv, op)
        else:
            # CP-SAT var vs "other" Python value: type mismatch.
            result = (op == "ne")  # ne: True; eq: False
        if result:
            # True only when both operands are defined (same reasoning as above).
            defs = [x for x in (ld, rd) if x is not True]
            if defs:
                model.add_bool_and([b]).only_enforce_if(defs)
                model.add_bool_and([~b]).only_enforce_if([~d for d in defs])
            else:
                model.add_bool_and([b])
        else:
            model.add_bool_and([~b])  # always False
        return b

    # Same kind, both constants.
    if lc and rc:
        if _const_cmp(lv, rv, op):
            model.add_bool_and([b])
        else:
            model.add_bool_and([~b])
        return b

    # At least one CP-SAT expression.
    # For the "~b ⟹ ~comparison" direction, only enforce when operands are defined.
    if op == "eq":
        model.add(lv == rv).only_enforce_if(b)
        model.add(lv != rv).only_enforce_if(not_b_and_defined)
    elif op == "ne":
        model.add(lv != rv).only_enforce_if(b)
        model.add(lv == rv).only_enforce_if(not_b_and_defined)
    elif op == "lt":
        model.add(lv < rv).only_enforce_if(b)
        model.add(lv >= rv).only_enforce_if(not_b_and_defined)
    elif op == "le":
        model.add(lv <= rv).only_enforce_if(b)
        model.add(lv > rv).only_enforce_if(not_b_and_defined)
    elif op == "gt":
        model.add(lv > rv).only_enforce_if(b)
        model.add(lv <= rv).only_enforce_if(not_b_and_defined)
    elif op == "ge":
        model.add(lv >= rv).only_enforce_if(b)
        model.add(lv < rv).only_enforce_if(not_b_and_defined)
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
