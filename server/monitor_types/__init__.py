from importlib import import_module
from pathlib import Path
from .monitor_type import MonitorType

# automatically import all monitor type modules
for _path in Path(__file__).parent.glob("*.py"):
    if _path.stem not in {"__init__", "monitor_type"}:
        import_module(f"{__name__}.{_path.stem}")

monitor_types = {cls.name: cls for cls in MonitorType.__subclasses__()}
_by_class_name = {cls.__name__: cls for cls in MonitorType.__subclasses__()}

# expose classes as module attributes for convenience
globals().update(_by_class_name)
