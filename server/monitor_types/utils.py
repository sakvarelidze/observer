from __future__ import annotations

import ssl
import jmespath

try:
    from server.db import models  # type: ignore
except Exception:  # pragma: no cover
    models = None


def evaluate_json_query(data: object, json_path: str | None, operator: str, expected_value: object) -> tuple[bool, object]:
    """Evaluate *json_path* on *data* and compare with *expected_value* using
    *operator*.
    Returns a tuple ``(status, result)`` where ``status`` is ``True`` if the
    comparison passes and ``result`` is the evaluated value.
    """
    result = jmespath.search(json_path, data) if json_path else data
    if result is None:
        raise ValueError("Empty or undefined response. Check query syntax and response structure")
    if isinstance(result, (dict, list)):
        raise ValueError(
            "The post-JSON query evaluated response from the server is of type "
            f"{type(result).__name__}, which cannot be directly compared to the expected value"
        )
    value = str(result)
    expected = str(expected_value)
    if operator in {">", ">=", "<", "<="}:
        try:
            value_f = float(value)
            expected_f = float(expected)
        except Exception:
            raise ValueError("Numeric comparison requires numeric values")
        compare = {
            ">": value_f > expected_f,
            ">=": value_f >= expected_f,
            "<": value_f < expected_f,
            "<=": value_f <= expected_f,
        }[operator]
    elif operator == "==":
        compare = value == expected
    elif operator == "!=":
        compare = value != expected
    elif operator == "contains":
        compare = expected in value
    else:
        raise ValueError(f"Invalid condition {operator}")
    return compare, result


def exception_message(exc: Exception) -> str:
    """Return a non-empty string describing *exc*.

    Certain exception types like :class:`asyncio.TimeoutError` have an empty
    string representation which leads to blank status messages in the UI.  This
    helper falls back to the exception class name when ``str(exc)`` is empty.
    """

    msg = str(exc)
    return msg if msg else exc.__class__.__name__


def ssl_ctx_for_monitor(m: "models.Monitor") -> ssl.SSLContext | bool:
    """Return an :class:`ssl.SSLContext` or ``False`` based on monitor settings.

    If ``m.tls_verify_mode`` is ``"insecure"`` or the legacy ``ignore_tls`` flag is
    true, ``False`` is returned to disable verification.  If ``tls_verify_mode`` is
    ``"presented_ca"`` and a custom CA is stored, the context is populated with it.
    Otherwise the default system context is returned.
    """

    mode = getattr(m, "tls_verify_mode", "system")
    if getattr(m, "ignore_tls", False) or mode == "insecure":
        return False
    ctx = ssl.create_default_context()
    if mode == "presented_ca" and getattr(m, "custom_ca_pem", None):
        ctx.load_verify_locations(cadata=m.custom_ca_pem)
        tf = getattr(ssl, "VERIFY_X509_TRUSTED_FIRST", 0)
        st = getattr(ssl, "VERIFY_X509_STRICT", 0)
        try:
            ctx.verify_flags = (ctx.verify_flags | tf) & (~st)
        except Exception:
            pass
    return ctx
