"""Name: the only source of symbolic identity in the new core."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Name:
    """Annotated-metadata marker that assigns a label to a subtree."""

    label: str
