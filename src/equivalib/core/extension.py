"""Extension protocol for registering custom leaf types with ``generate``.

Public API:
    Extension  – structural protocol that extension objects must satisfy.
"""

from __future__ import annotations

from typing import Collection, Iterator, Sequence


class Extension:
    """Protocol for extension objects passed to ``generate(extensions=...)``.

    Extension objects must implement all four methods below.  Any class with
    these methods qualifies – there is no need to inherit from ``Extension``
    directly.

    Methods:
        initialize(tree, constraint) -> Expression | None
            Called once per ``generate`` invocation, before normalization.
            May return an additional boolean ``Expression`` to be AND-ed with
            the user's constraint, or ``None`` to add no extra constraint.

        enumerate_all(owner) -> Iterator
            Yield all values in the domain of ``owner``.  Must terminate for
            finite domains; MAY raise ``ValueError`` for infinite domains
            (in which case the ``"arbitrary"`` method is the only supported
            witness strategy for that label).

        arbitrary(owner, values=None) -> object
            Return a deterministic canonical witness.
            If ``values`` is ``None``, choose from the full domain of ``owner``.
            If ``values`` is a non-empty collection, choose from it instead.

        uniform_random(owner, weighted_values=None) -> object
            Return a randomly sampled witness.
            If ``weighted_values`` is ``None``, sample from the full domain.
            If ``weighted_values`` is a non-empty sequence of ``(value, count)``
            pairs, sample weighted by count.
            MUST raise ``ValueError`` for infinite domains when called without
            ``weighted_values`` (i.e. when sampling cannot be done correctly).
    """

    def initialize(self, tree: object, constraint: object) -> object:
        """Return an extra boolean constraint or ``None``."""
        raise NotImplementedError

    def enumerate_all(self, owner: object) -> Iterator[object]:
        """Yield all domain values for ``owner``."""
        raise NotImplementedError

    def arbitrary(self, owner: object, values: Collection[object] | None = None) -> object:
        """Return a deterministic witness from ``values`` (or the full domain)."""
        raise NotImplementedError

    def uniform_random(self, owner: object, weighted_values: Sequence[tuple[object, int]] | None = None) -> object:
        """Return a randomly sampled witness."""
        raise NotImplementedError
