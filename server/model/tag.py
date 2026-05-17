from __future__ import annotations
from dataclasses import dataclass

@dataclass
class Tag:
    """Simple dataclass mirror of the Tag ORM model."""

    id: int | None = None
    name: str | None = None
    color: str | None = None

    def to_json(self):
        return self.__dict__
