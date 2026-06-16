import os
import sys

import pytest

sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
)


@pytest.fixture(autouse=True)
def _clear_uptime_cache():
    """The status-page uptime aggregates are cached process-wide with a TTL.
    Tests reuse monitor IDs across fresh databases, so a value cached by one
    test would otherwise satisfy the next test's lookup and return stale
    figures. Clear it around every test for isolation."""
    import server.routers.api as api

    api._uptime_cache.clear()
    yield
    api._uptime_cache.clear()
