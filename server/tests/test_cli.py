import os
import sys
import importlib
import types
import builtins
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

import server.server as server

@pytest.fixture(autouse=True)
def clear_argv():
    old = sys.argv[:]
    yield
    sys.argv[:] = old


def test_main_invokes_uvicorn(monkeypatch):
    called = {}
    def fake_run(app, host="", port=0):
        called["host"] = host
        called["port"] = port
        called["app"] = app
    monkeypatch.setattr("uvicorn.run", fake_run)
    sys.argv = ["server.py"]
    server.main()
    assert called["app"] is server.app
    assert called["host"] == "0.0.0.0"
    assert called["port"] == 3001
