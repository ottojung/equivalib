"""Super-method reduction: from S0 (all satisfying assignments) to S* (final set).

Public API:
    apply_methods(assignments, methods) -> list[dict]

Processes labels in ascending lexicographic order.
"""

from __future__ import annotations

import random
from typing import Any, Mapping

from equivalib.core.order import canonical_first


def apply_methods(assignments: list, methods: Mapping[str, str]) -> list:
    """Reduce the satisfying-assignment set ``assignments`` using ``methods``.

    Labels without an explicit method default to ``"all"``.

    Algorithm:
        1. Start with S := assignments.
        2. Process each label in lexicographic order.
        3. For ``"all"``: no filtering.
        4. For others: choose a witness value, then filter S.
    """
    if not assignments:
        return []

    # Collect all labels present in any assignment.
    all_labels = sorted({label for asgn in assignments for label in asgn})

    current = list(assignments)

    for label in all_labels:
        method = methods.get(label, "all")

        if method == "all":
            continue

        projection = _project(label, current)

        if not projection:
            # No values: can't select a witness, return empty.
            return []

        witness = _choose_witness(method, label, projection)
        current = [a for a in current if a.get(label) == witness]

    return current


def _project(label: str, assignments: list) -> list:
    """Return the list of values taken by ``label`` across ``assignments`` (with multiplicity)."""
    return [a[label] for a in assignments if label in a]


def _choose_witness(method: str, label: str, projection: list) -> Any:
    """Choose a single witness value from ``projection`` according to ``method``."""
    distinct = list(dict.fromkeys(projection))  # preserves order, deduplicates

    if method == "arbitrary":
        return canonical_first(distinct)

    if method == "uniform_random":
        # Weighted by the number of satisfying assignments supporting each value.
        return random.choices(projection, k=1)[0]

    if method == "arbitrarish_randomish":
        # Uniform over distinct projected values.
        return random.choice(distinct)

    raise ValueError(f"Unknown method {method!r} for label {label!r}.")
