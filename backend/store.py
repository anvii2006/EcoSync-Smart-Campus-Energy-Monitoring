"""A keyed store shared by the energy service's AWS and local entry points."""

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class Put:
    pk: str
    sk: str
    value: dict
    guard: Optional[tuple] = None


@dataclass(frozen=True)
class Increment:
    pk: str
    sk: str
    fields: dict


class Conflict(Exception):
    """The room or settings changed after the caller read them."""
