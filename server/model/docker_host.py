from __future__ import annotations
from dataclasses import dataclass

@dataclass
class DockerHost:
    id: int | None = None
    # additional fields would go here

    def to_json(self):
        return self.__dict__
