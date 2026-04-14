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

from typing import Any

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
# Full evaluation (all labels must be assigned)
# ---------------------------------------------------------------------------

def eval_expression(expr: object, assignment: dict) -> Any:
    """Evaluate ``expr`` against a complete assignment mapping.

    ``assignment`` maps label strings to runtime values.
    Raises ``KeyError`` if a referenced label is absent.
    """
    return _eval(expr, assignment)


def _eval(expr: object, assignment: dict) -> Any:
    if isinstance(expr, BooleanConstant):
        return expr.value
    if isinstance(expr, IntegerConstant):
        return expr.value
    if isinstance(expr, Reference):
        value = assignment[expr.label]
        for idx in expr.path:
            value = value[idx]
        return value
    if isinstance(expr, Neg):
        return -_eval(expr.operand, assignment)
    if isinstance(expr, Add):
        return _eval(expr.left, assignment) + _eval(expr.right, assignment)
    if isinstance(expr, Sub):
        return _eval(expr.left, assignment) - _eval(expr.right, assignment)
    if isinstance(expr, Mul):
        return _eval(expr.left, assignment) * _eval(expr.right, assignment)
    if isinstance(expr, FloorDiv):
        return _eval(expr.left, assignment) // _eval(expr.right, assignment)
    if isinstance(expr, Mod):
        return _eval(expr.left, assignment) % _eval(expr.right, assignment)
    if isinstance(expr, Eq):
        return _eval(expr.left, assignment) == _eval(expr.right, assignment)
    if isinstance(expr, Ne):
        return _eval(expr.left, assignment) != _eval(expr.right, assignment)
    if isinstance(expr, Lt):
        return _eval(expr.left, assignment) < _eval(expr.right, assignment)
    if isinstance(expr, Le):
        return _eval(expr.left, assignment) <= _eval(expr.right, assignment)
    if isinstance(expr, Gt):
        return _eval(expr.left, assignment) > _eval(expr.right, assignment)
    if isinstance(expr, Ge):
        return _eval(expr.left, assignment) >= _eval(expr.right, assignment)
    if isinstance(expr, And):
        return _eval(expr.left, assignment) and _eval(expr.right, assignment)
    if isinstance(expr, Or):
        return _eval(expr.left, assignment) or _eval(expr.right, assignment)
    raise TypeError(f"Unknown expression node: {type(expr)}")


# ---------------------------------------------------------------------------
# Partial evaluation (some labels may be unresolved)
# ---------------------------------------------------------------------------

def eval_expression_partial(expr: object, partial_assignment: dict) -> Any:
    """Evaluate ``expr`` against a partial assignment.

    Returns a concrete value if it can be determined, or ``Unknown`` if the
    result depends on an unbound label.
    """
    return _eval_partial(expr, partial_assignment)


def _eval_partial(expr: object, pa: dict) -> Any:
    if isinstance(expr, BooleanConstant):
        return expr.value
    if isinstance(expr, IntegerConstant):
        return expr.value
    if isinstance(expr, Reference):
        if expr.label not in pa:
            return Unknown
        value = pa[expr.label]
        for idx in expr.path:
            if isinstance(value, _UnknownType):
                return Unknown
            value = value[idx]
        return value
    if isinstance(expr, Neg):
        v = _eval_partial(expr.operand, pa)
        if isinstance(v, _UnknownType):
            return Unknown
        return -v
    if isinstance(expr, (Add, Sub, Mul, FloorDiv, Mod)):
        lv = _eval_partial(expr.left, pa)
        rv = _eval_partial(expr.right, pa)
        if isinstance(lv, _UnknownType) or isinstance(rv, _UnknownType):
            return Unknown
        if isinstance(expr, Add):
            return lv + rv
        if isinstance(expr, Sub):
            return lv - rv
        if isinstance(expr, Mul):
            return lv * rv
        if isinstance(expr, FloorDiv):
            return lv // rv
        return lv % rv
    if isinstance(expr, (Eq, Ne, Lt, Le, Gt, Ge)):
        lv = _eval_partial(expr.left, pa)
        rv = _eval_partial(expr.right, pa)
        if isinstance(lv, _UnknownType) or isinstance(rv, _UnknownType):
            return Unknown
        if isinstance(expr, Eq):
            return lv == rv
        if isinstance(expr, Ne):
            return lv != rv
        if isinstance(expr, Lt):
            return lv < rv
        if isinstance(expr, Le):
            return lv <= rv
        if isinstance(expr, Gt):
            return lv > rv
        return lv >= rv
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
    raise TypeError(f"Unknown expression node: {type(expr)}")
