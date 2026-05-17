from __future__ import annotations
from dataclasses import dataclass

@dataclass
class User:
    id: int | None = None
    # additional fields would go here

    def to_json(self):
        return self.__dict__
