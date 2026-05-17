from __future__ import annotations

from importlib import import_module
from pathlib import Path

from .base import NotificationProvider

# Dynamically import all provider modules in this package
for _path in Path(__file__).parent.glob("*.py"):
    if _path.stem not in {"__init__", "base"}:
        import_module(f"{__name__}.{_path.stem}")

providers = {cls.name: cls() for cls in NotificationProvider.__subclasses__()}

def get_provider(name: str) -> NotificationProvider | None:
    return providers.get(name)
