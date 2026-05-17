import types
import pytest

import server.monitor_types.snmp as snmp_mod
from server.monitor_types.snmp import Snmp


class FakeSnmpClient:
    last_instance = None

    def __init__(self, host, community, port=161, response=None):
        self.host = host
        self.community = community
        self.port = port
        self._response = response
        FakeSnmpClient.last_instance = self

    async def get(self, oid):
        if isinstance(self._response, Exception):
            raise self._response
        return self._response


@pytest.fixture
def patch_snmp(monkeypatch):
    def make(response):
        def factory(host, community, port=161):
            return FakeSnmpClient(host, community, port=port, response=response)
        monkeypatch.setattr(snmp_mod, "Client", factory)
        monkeypatch.setattr(snmp_mod, "V2C", lambda c: c)
        monkeypatch.setattr(snmp_mod, "ObjectIdentifier", lambda o: o)
    return make


@pytest.mark.asyncio
async def test_snmp_monitor_success_reachability_only(patch_snmp):
    """Monitor with no expectedValue and no jsonPath: succeed on reachability."""
    patch_snmp(42)
    monitor = types.SimpleNamespace(
        hostname="192.0.2.1",
        port=161,
        snmpOid="1.3.6.1.2.1.1.1.0",
        radiusPassword="public",
    )
    hb = types.SimpleNamespace(status=None, msg=None)
    await Snmp().check(monitor, hb)
    assert hb.status == 1
    assert "OK" in hb.msg
    assert "42" in hb.msg


@pytest.mark.asyncio
async def test_snmp_monitor_success_with_matching_value(patch_snmp):
    patch_snmp(42)
    monitor = types.SimpleNamespace(
        hostname="192.0.2.1",
        port=161,
        snmpOid="1.3.6.1.2.1.1.1.0",
        radiusPassword="public",
        expectedValue=42,
        jsonPathOperator="==",
    )
    hb = types.SimpleNamespace(status=None, msg=None)
    await Snmp().check(monitor, hb)
    assert hb.status == 1
    assert "JSON query passes" in hb.msg


@pytest.mark.asyncio
async def test_snmp_monitor_missing_oid():
    monitor = types.SimpleNamespace(
        hostname="192.0.2.1",
        snmpOid=None,
    )
    hb = types.SimpleNamespace(status=None, msg=None)
    with pytest.raises(ValueError):
        await Snmp().check(monitor, hb)


@pytest.mark.asyncio
async def test_snmp_monitor_missing_host():
    monitor = types.SimpleNamespace(
        hostname=None,
        snmpOid="1.3.6.1.2.1.1.1.0",
    )
    hb = types.SimpleNamespace(status=None, msg=None)
    with pytest.raises(ValueError):
        await Snmp().check(monitor, hb)


@pytest.mark.asyncio
async def test_snmp_monitor_get_failure(patch_snmp):
    patch_snmp(TimeoutError("no response"))
    monitor = types.SimpleNamespace(
        hostname="192.0.2.1",
        snmpOid="1.3.6.1.2.1.1.1.0",
    )
    hb = types.SimpleNamespace(status=None, msg=None)
    await Snmp().check(monitor, hb)
    assert hb.status == 0
    assert "no response" in hb.msg


@pytest.mark.asyncio
async def test_snmp_monitor_expected_value_mismatch(patch_snmp):
    patch_snmp(7)
    monitor = types.SimpleNamespace(
        hostname="192.0.2.1",
        snmpOid="1.3.6.1.2.1.1.1.0",
        expectedValue=42,
        jsonPathOperator="==",
    )
    hb = types.SimpleNamespace(status=None, msg=None)
    await Snmp().check(monitor, hb)
    assert hb.status == 0
    assert "does not pass" in hb.msg
