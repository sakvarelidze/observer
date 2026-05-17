from __future__ import annotations

import asyncio
import json

from pymongo import MongoClient

from .monitor_type import MonitorType
from .utils import evaluate_json_query, exception_message


class Mongodb(MonitorType):
    """Basic connectivity check for MongoDB."""

    name = "mongodb"

    async def check(self, monitor, heartbeat, server=None):
        conn = getattr(monitor, "databaseConnectionString", None)
        timeout = getattr(monitor, "timeout", 10)
        query = getattr(monitor, "databaseQuery", None)
        json_path = getattr(monitor, "jsonPath", None)
        expected_value = getattr(monitor, "expectedValue", None)
        operator = getattr(monitor, "jsonPathOperator", "==")

        if not conn:
            raise ValueError("Monitor must define a databaseConnectionString")

        command: dict = {"ping": 1}
        if query:
            try:
                command = json.loads(query)
            except Exception as exc:
                raise ValueError("Invalid MongoDB query") from exc

        client = MongoClient(conn, serverSelectionTimeoutMS=timeout * 1000)
        try:
            result = await asyncio.get_running_loop().run_in_executor(
                None, lambda: client.get_database().command(command)
            )

            msg = "Command executed successfully"
            if json_path or expected_value is not None:
                status, value = evaluate_json_query(
                    result, json_path, operator, expected_value
                )
                if status:
                    msg = (
                        "Command executed successfully and expected value was found"
                        if expected_value is not None
                        else "Command executed successfully and the jsonpath expression produces a result."
                    )
                else:
                    raise ValueError(
                        f"Query executed but value is not equal to expected value, value was: [{value}]"
                    )
            heartbeat.status = 1
            heartbeat.msg = msg
        except Exception as exc:  # pragma: no cover - network issues possible
            heartbeat.status = 0
            heartbeat.msg = exception_message(exc)
        finally:
            client.close()
