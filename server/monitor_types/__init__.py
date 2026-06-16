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

# Types whose state is delivered externally (e.g. push heartbeats) rather
# than discovered by an outbound probe. These must never be actively
# checked: there's no registered probe class for them, so the
# `monitor_types.get(type, HTTPMonitor)` fallback would otherwise fire a
# bogus HTTP request at the monitor's URL and overwrite the pushed status.
PASSIVE_MONITOR_TYPES = {"push"}


def is_actively_probed(monitor_type) -> bool:
    """True when a monitor of this type should be probed on a schedule /
    on creation. Passive types (push) receive their heartbeats from an
    external caller instead."""
    return (monitor_type or "").lower() not in PASSIVE_MONITOR_TYPES
