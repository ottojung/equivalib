"""Super-method reduction: from S0 (all satisfying assignments) to S* (final set).

Public API:
    apply_methods(assignments, methods, label_order) -> list[dict]

Processes labels in structural tree order (first-appearance order during
left-to-right DFS traversal of the input type tree).
"""

from __future__ import annotations

import random
from typing import Literal, Mapping, TypeAlias

from equivalib.core.order import canonical_first

Label: TypeAlias = str
Method: TypeAlias = Literal["all", "arbitrary", "uniform_random"]


def apply_methods(
    assignments: list[dict[str, object]],
    methods: Mapping[Label, Method],
    label_order: list[str],
    extension_hooks: dict[str, tuple[object, object]] | None = None,
) -> list[dict[str, object]]:
    """Reduce the satisfying-assignment set ``assignments`` using ``methods``.

    Labels without an explicit method default to ``"all"``.

    ``extension_hooks`` maps label -> ``(ext_obj, owner)`` for extension-owned
    labels so that ``arbitrary`` and ``uniform_random`` delegate to the
    extension's own hook rather than the default canonical policy.

    Algorithm:
        1. Start with S := assignments.
        2. Process each label in structural tree order (first-appearance order
           during left-to-right DFS traversal).  This order is independent of
           label names, ensuring that consistent renaming of all occurrences of
           a label (alpha conversion) does not change the output.
        3. For ``"all"``: no filtering.
        4. For others: choose a witness value, then filter S.
    """
    if not assignments:
        return []

    hooks = extension_hooks or {}

    # Use structural order: labels appear in the order they were first seen
    # during a left-to-right DFS traversal of the type tree.  This guarantees
    # alpha-conversion invariance: renaming labels consistently cannot change
    # the processing order and therefore cannot change the output.
    assignment_labels = {label for asgn in assignments for label in asgn}
    missing_labels = sorted(assignment_labels.difference(label_order))
    if missing_labels:
        raise ValueError(
            "label_order is missing labels present in assignments: "
            + ", ".join(repr(label) for label in missing_labels)
        )
    ordered_labels = [lbl for lbl in label_order if lbl in assignment_labels]

    current = list(assignments)

    for label in ordered_labels:
        method = methods.get(label, "all")

        if method == "all":
            continue

        projection = _project(label, current)

        if not projection:
            # No values: can't select a witness, return empty.
            return []

        if label in hooks and method in ("arbitrary", "uniform_random"):
            witness = _choose_witness_ext(method, label, projection, hooks[label])
        else:
            witness = _choose_witness(method, label, projection)
        current = [
            a for a in current if label in a and _structural_eq(a[label], witness)
        ]

    return current


def _project(label: str, assignments: list[dict[str, object]]) -> list[object]:
    """Return the list of values taken by ``label`` across ``assignments`` (with multiplicity)."""
    return [a[label] for a in assignments if label in a]


def _choose_witness_ext(method: str, label: str, projection: list[object], hook: tuple[object, object]) -> object:
    """Choose a witness using the extension hook for ``method``."""
    ext_obj, owner = hook
    distinct: list[object] = []
    seen_tags: set[object] = set()
    for value in projection:
        tagged = _tag_value(value)
        if tagged not in seen_tags:
            seen_tags.add(tagged)
            distinct.append(value)

    if method == "arbitrary":
        candidate = ext_obj.arbitrary(owner, None)  # type: ignore[union-attr]
    elif method == "uniform_random":
        candidate = ext_obj.uniform_random(owner, None)  # type: ignore[union-attr]
    else:
        raise ValueError(f"Unknown method {method!r} for label {label!r}.")

    if _tag_value(candidate) in seen_tags:
        return candidate
    # Candidate is not admissible; fall back to canonical first.
    return canonical_first(distinct)


def _choose_witness(method: str, label: str, projection: list[object]) -> object:
    """Choose a single witness value from ``projection`` according to ``method``."""
    distinct: list[object] = []
    seen: set[object] = set()
    for value in projection:
        tagged = _tag_value(value)
        if tagged in seen:
            continue
        seen.add(tagged)
        distinct.append(value)

    if method == "arbitrary":
        return canonical_first(distinct)

    if method == "uniform_random":
        # Weighted by the number of satisfying assignments supporting each value.
        return random.choices(projection, k=1)[0]

    raise ValueError(f"Unknown method {method!r} for label {label!r}.")


def _tag_value(v: object) -> object:
    """Return a recursively type-tagged representation for type-aware equality."""
    # bool is a subclass of int, so this check must come first.
    if isinstance(v, bool):
        return (bool, v)
    if isinstance(v, int):
        return (int, v)
    if isinstance(v, tuple):
        return (tuple, tuple(_tag_value(elem) for elem in v))
    return (type(v), v)


def _structural_eq(lhs: object, rhs: object) -> bool:
    """Type-aware structural equality (bool/int are distinct, incl. tuples)."""
    return _tag_value(lhs) == _tag_value(rhs)
