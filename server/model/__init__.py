from importlib import import_module
from pathlib import Path

# Dynamically import all model stubs
for _path in Path(__file__).parent.glob("*.py"):
    if _path.stem != "__init__":
        import_module(f"{__name__}.{_path.stem}")
