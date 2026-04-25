"""Expression evaluation (full and partial) for the new core.

Public API:
    eval_expression(expr, assignment) -> bool | int | ...
    eval_expression_partial(expr, partial_assignment) -> bool | int | ... | Unknown

``Unknown`` is a sentinel object for the three-valued partial evaluation.

Partial evaluation rules support short-circuit pruning:
    And(False, Unknown) -> False
    And(True, Unknown)  -> Unknown
    Or(True, Unknown)   -> True
    Or(False, Unknown)  -> Unknown
"""

from __future__ import annotations

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


# ---------------------------------------------------------------------------
# Unknown sentinel
# ---------------------------------------------------------------------------

class _UnknownType:
    """Singleton sentinel for unknown (unresolved) partial values."""

    _instance = None

    def __new__(cls) -> "_UnknownType":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __repr__(self) -> str:
        return "Unknown"


Unknown = _UnknownType()


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
# Structural equality helper
# ---------------------------------------------------------------------------

def _structural_eq(lv: object, rv: object) -> bool:
    """Type-aware structural equality.

    Python's ``True == 1`` (and ``(True,) == (1,)``) conflates bool and int.
    This helper first checks that ``type(lv) is type(rv)``, then recurses
    element-wise for tuples, so that values of different types are always
    considered distinct.
    """
    if type(lv) is not type(rv):
        return False
    if isinstance(lv, tuple) and isinstance(rv, tuple):
        if len(lv) != len(rv):
            return False
        return all(_structural_eq(a, b) for a, b in zip(lv, rv))
    return lv == rv


# ---------------------------------------------------------------------------
# Full evaluation (all labels must be assigned)
# ---------------------------------------------------------------------------

def eval_expression(expr: Expression, assignment: dict[str, object]) -> object:
    """Evaluate ``expr`` against a complete assignment mapping.

    ``assignment`` maps label strings to runtime values.
    Raises ``KeyError`` if a referenced label is absent.
    """
    return _eval(expr, assignment)


def _eval(expr: Expression, assignment: dict[str, object]) -> object:
    if isinstance(expr, BooleanConstant):
        return expr.value
    if isinstance(expr, IntegerConstant):
        return expr.value
    if isinstance(expr, Reference):
        value: object = assignment[expr.label]
        return _follow_reference_path(value, expr.path, expr.label)
    if isinstance(expr, Neg):
        return -_eval(expr.operand, assignment)  # type: ignore[operator]
    if isinstance(expr, Add):
        return _eval(expr.left, assignment) + _eval(expr.right, assignment)  # type: ignore[operator]
    if isinstance(expr, Sub):
        return _eval(expr.left, assignment) - _eval(expr.right, assignment)  # type: ignore[operator]
    if isinstance(expr, Mul):
        return _eval(expr.left, assignment) * _eval(expr.right, assignment)  # type: ignore[operator]
    if isinstance(expr, FloorDiv):
        return _eval(expr.left, assignment) // _eval(expr.right, assignment)  # type: ignore[operator]
    if isinstance(expr, Mod):
        return _eval(expr.left, assignment) % _eval(expr.right, assignment)  # type: ignore[operator]
    if isinstance(expr, Eq):
        return _structural_eq(_eval(expr.left, assignment), _eval(expr.right, assignment))
    if isinstance(expr, Ne):
        return not _structural_eq(_eval(expr.left, assignment), _eval(expr.right, assignment))
    if isinstance(expr, Lt):
        return _eval(expr.left, assignment) < _eval(expr.right, assignment)  # type: ignore[operator]
    if isinstance(expr, Le):
        return _eval(expr.left, assignment) <= _eval(expr.right, assignment)  # type: ignore[operator]
    if isinstance(expr, Gt):
        return _eval(expr.left, assignment) > _eval(expr.right, assignment)  # type: ignore[operator]
    if isinstance(expr, Ge):
        return _eval(expr.left, assignment) >= _eval(expr.right, assignment)  # type: ignore[operator]
    if isinstance(expr, And):
        return _eval(expr.left, assignment) and _eval(expr.right, assignment)
    if isinstance(expr, Or):
        return _eval(expr.left, assignment) or _eval(expr.right, assignment)
    impossible(expr)


# ---------------------------------------------------------------------------
# Partial evaluation (some labels may be unresolved)
# ---------------------------------------------------------------------------

def eval_expression_partial(expr: Expression, partial_assignment: dict[str, object]) -> object:
    """Evaluate ``expr`` against a partial assignment.

    Returns a concrete value if it can be determined, or ``Unknown`` if the
    result depends on an unbound label.
    """
    return _eval_partial(expr, partial_assignment)


def _eval_partial(expr: Expression, pa: dict[str, object]) -> object:
    if isinstance(expr, BooleanConstant):
        return expr.value
    if isinstance(expr, IntegerConstant):
        return expr.value
    if isinstance(expr, Reference):
        if expr.label not in pa:
            return Unknown
        value: object = pa[expr.label]
        for prefix_len in range(len(expr.path) + 1):
            if isinstance(value, _UnknownType):
                return Unknown
            if prefix_len == len(expr.path):
                return value
            idx = expr.path[prefix_len]
            if not isinstance(value, tuple):
                raise TypeError(
                    f"Reference {expr.label!r} path {expr.path!r} descends into non-tuple "
                    f"at depth {prefix_len}: {value!r}."
                )
            if idx < 0 or idx >= len(value):
                raise IndexError(
                    f"Reference {expr.label!r} path {expr.path!r} uses out-of-range zero-based "
                    f"index {idx} at depth {prefix_len} for tuple length {len(value)}."
                )
            value = value[idx]
        return value
    if isinstance(expr, Neg):
        v = _eval_partial(expr.operand, pa)
        if isinstance(v, _UnknownType):
            return Unknown
        return -v  # type: ignore[operator]
    if isinstance(expr, (Add, Sub, Mul, FloorDiv, Mod)):
        lv = _eval_partial(expr.left, pa)
        rv = _eval_partial(expr.right, pa)
        if isinstance(lv, _UnknownType) or isinstance(rv, _UnknownType):
            return Unknown
        if isinstance(expr, Add):
            return lv + rv  # type: ignore[operator]
        if isinstance(expr, Sub):
            return lv - rv  # type: ignore[operator]
        if isinstance(expr, Mul):
            return lv * rv  # type: ignore[operator]
        if isinstance(expr, FloorDiv):
            return lv // rv  # type: ignore[operator]
        return lv % rv  # type: ignore[operator]
    if isinstance(expr, (Eq, Ne, Lt, Le, Gt, Ge)):
        lv = _eval_partial(expr.left, pa)
        rv = _eval_partial(expr.right, pa)
        if isinstance(lv, _UnknownType) or isinstance(rv, _UnknownType):
            return Unknown
        if isinstance(expr, Eq):
            return _structural_eq(lv, rv)
        if isinstance(expr, Ne):
            return not _structural_eq(lv, rv)
        if isinstance(expr, Lt):
            return lv < rv  # type: ignore[operator]
        if isinstance(expr, Le):
            return lv <= rv  # type: ignore[operator]
        if isinstance(expr, Gt):
            return lv > rv  # type: ignore[operator]
        return lv >= rv  # type: ignore[operator]
    if isinstance(expr, And):
        lv = _eval_partial(expr.left, pa)
        if lv is False:
            return False  # Short-circuit: And(False, *) = False
        rv = _eval_partial(expr.right, pa)
        if rv is False:
            return False
        if isinstance(lv, _UnknownType) or isinstance(rv, _UnknownType):
            return Unknown
        return lv and rv
    if isinstance(expr, Or):
        lv = _eval_partial(expr.left, pa)
        if lv is True:
            return True  # Short-circuit: Or(True, *) = True
        rv = _eval_partial(expr.right, pa)
        if rv is True:
            return True
        if isinstance(lv, _UnknownType) or isinstance(rv, _UnknownType):
            return Unknown
        return lv or rv
    impossible(expr)
