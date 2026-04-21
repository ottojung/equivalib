"""Super-method reduction: from S0 (all satisfying assignments) to S* (final set).

Public API:
    apply_methods(assignments, methods, label_order, ext_hooks) -> list[dict]

Processes labels in structural tree order (first-appearance order during
left-to-right DFS traversal of the input type tree).
"""

from __future__ import annotations

import random
from typing import Any, Literal, Mapping, TypeAlias

from equivalib.core.order import canonical_first

Label: TypeAlias = str
Method: TypeAlias = Literal["all", "arbitrary", "uniform_random"]


def apply_methods(
    assignments: list[dict[str, object]],
    methods: Mapping[Label, Method],
    label_order: list[str],
    ext_hooks: dict[str, tuple[object, Any, list[object]]] | None = None,
) -> list[dict[str, object]]:
    """Reduce the satisfying-assignment set ``assignments`` using ``methods``.

    Labels without an explicit method default to ``"all"``.

    ``ext_hooks`` maps label → (owner, extension_object, domain_order) for
    extension-owned labels.  When a label has an entry in ``ext_hooks``, the
    extension's ``arbitrary`` / ``uniform_random`` methods are called instead
    of the built-in selection strategies.

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
            return []

        if ext_hooks and label in ext_hooks:
            owner, extension, domain_order = ext_hooks[label]
            witness = _choose_witness_ext(method, label, projection, owner, extension, domain_order)
        else:
            witness = _choose_witness(method, label, projection)

        if witness is None:
            return []

        current = [
            a for a in current if label in a and _structural_eq(a[label], witness)
        ]

    return current


def _project(label: str, assignments: list[dict[str, object]]) -> list[object]:
    """Return the list of values taken by ``label`` across ``assignments`` (with multiplicity)."""
    return [a[label] for a in assignments if label in a]


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


def _choose_witness_ext(
    method: str,
    label: str,
    projection: list[object],
    owner: object,
    extension: Any,
    domain_order: list[object] | None = None,
) -> object:
    """Choose a witness using the extension's method hook.

    When *domain_order* is provided:
    - If all domain values are represented in *projection*, passes ``None``
      to the extension so it can use its own domain ordering.
    - Otherwise passes the admissible values (sorted by domain order) to
      the extension, enabling constraint-aware selection.
    """
    distinct: list[object] = []
    seen: set[object] = set()
    for value in projection:
        tagged = _tag_value(value)
        if tagged in seen:
            continue
        seen.add(tagged)
        distinct.append(value)

    # Sort distinct values by original domain order (if known).
    if domain_order:
        domain_index = {_tag_value(v): i for i, v in enumerate(domain_order)}
        distinct.sort(key=lambda v: domain_index.get(_tag_value(v), len(domain_order)))

    # Pass None (let extension use its own ordering) when all domain values are admissible.
    all_admissible = bool(domain_order) and len(distinct) == len(domain_order)

    if method == "arbitrary":
        if all_admissible:
            return extension.arbitrary(owner, values=None)
        return extension.arbitrary(owner, values=distinct)

    if method == "uniform_random":
        if all_admissible:
            return extension.uniform_random(owner, weighted_values=None)
        # Build weighted_values in domain order.
        counts: dict[object, list[Any]] = {}
        for v in projection:
            tagged = _tag_value(v)
            if tagged not in counts:
                counts[tagged] = [v, 0]
            counts[tagged][1] += 1
        if domain_order:
            weighted_values = [
                (counts[_tag_value(v)][0], counts[_tag_value(v)][1])
                for v in domain_order
                if _tag_value(v) in counts
            ]
        else:
            weighted_values = [(info[0], info[1]) for info in counts.values()]
        return extension.uniform_random(owner, weighted_values=weighted_values)

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
