
from typing import Any

try:
    from ortools.sat.python.cp_model import LinearExprT
except ModuleNotFoundError:  # pragma: no cover - exercised in minimal environments
    LinearExprT = Any

Comparable = LinearExprT
