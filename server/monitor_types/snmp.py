from __future__ import annotations

import asyncio

from puresnmp import Client, ObjectIdentifier, V2C

from .monitor_type import MonitorType
from .utils import evaluate_json_query, exception_message


class Snmp(MonitorType):
    """Very lightweight SNMP reachability check."""

    name = "snmp"

    async def check(self, monitor, heartbeat, server=None):
        host = getattr(monitor, "hostname", None)
        port = getattr(monitor, "port", 161)
        community = getattr(monitor, "radiusPassword", "public")
        oid = getattr(monitor, "snmpOid", None)
        timeout = getattr(monitor, "timeout", 10)
        json_path = getattr(monitor, "jsonPath", None)
        operator = getattr(monitor, "jsonPathOperator", "==")
        expected_value = getattr(monitor, "expectedValue", None)

        if not host or not oid:
            raise ValueError("Monitor must define hostname and snmpOid")

        client = Client(host, V2C(community), port=int(port))
        try:
            result = await asyncio.wait_for(
                client.get(ObjectIdentifier(oid)), timeout=timeout
            )
            if json_path or expected_value is not None:
                status, value = evaluate_json_query(result, json_path, operator, expected_value)
                if status:
                    heartbeat.status = 1
                    heartbeat.msg = f"JSON query passes (comparing {value} {operator} {expected_value})"
                else:
                    raise ValueError(
                        f"JSON query does not pass (comparing {value} {operator} {expected_value})"
                    )
            else:
                heartbeat.status = 1
                heartbeat.msg = f"OK ({result})"
        except Exception as exc:  # pragma: no cover - network errors possible
            heartbeat.status = 0
            heartbeat.msg = exception_message(exc)
