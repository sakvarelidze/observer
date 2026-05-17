from __future__ import annotations
from typing import Dict, List, Optional

# Status verb for "up" alerts. Swap to "went UP" if you prefer the symmetric form.
UP_VERB = "came back UP"

# Status glyph per event. Peer status-tools (Uptime Kuma, Better Stack,
# Pingdom) all prefix alerts with a coloured marker — it's how the alert
# is scannable in a busy chat. Single-codepoint emoji that render
# consistently across Telegram / Slack / Discord / iOS / Android.
STATUS_GLYPH = {
    "down": "🔴",
    "up": "🟢",
    "paused": "⏸",
    "resumed": "▶",
    "test": "🔔",
    "slow": "🟡",
}

# Hex (with leading #) per event. Slack attachments / Discord embeds /
# Teams MessageCards all want a single brand color per event so the alert
# carries a coloured stripe or border. These are the same values the v2
# UI uses for its status pills (HSL converted to hex).
STATUS_COLOR_HEX = {
    "down": "#E81123",
    "up": "#16C60C",
    "paused": "#FFB900",
    "resumed": "#16C60C",
    "test": "#3B82F6",
    "slow": "#FFB900",
}

_TYPE_LABELS = {
    "http": "HTTP",
    "keyword": "HTTP keyword",
    "json": "HTTP JSON",
    "json-query": "HTTP JSON",
    "ping": "Ping",
    "icmp": "Ping",
    "dns": "DNS",
    "port": "Port",
    "push": "Push",
    "grpc": "gRPC",
    "grpc-keyword": "gRPC keyword",
    "tcp": "TCP",
    "udp": "UDP",
    "real-browser": "Browser",
}


def _type_label(m_type: Optional[str]) -> str:
    if not m_type:
        return ""
    return _TYPE_LABELS.get(m_type.strip().lower(), m_type.upper())


def _html_escape(s: str) -> str:
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _color_for(event: str) -> str:
    return STATUS_COLOR_HEX.get(event, "#6B7280")


def _extract_heartbeat(heartbeat: Optional[Dict]) -> Dict:
    """Pull error message + response time out of a raw heartbeat dict."""
    error_msg = ""
    response_ms: Optional[int] = None
    if heartbeat:
        msg = (heartbeat.get("msg") or heartbeat.get("message") or "").strip()
        code = heartbeat.get("code") or heartbeat.get("statusCode")
        if msg:
            if code and str(code) not in msg:
                error_msg = f"{msg} ({code})"
            else:
                error_msg = msg
        elif code:
            error_msg = f"HTTP {code}"
        ping = heartbeat.get("ping")
        if ping is not None:
            try:
                response_ms = int(ping)
            except (TypeError, ValueError):
                pass
    return {"error_msg": error_msg, "response_ms": response_ms}


def build_status_message(
    *,
    event: str,                # "up" | "down" | "paused" | "resumed" | "test"
    monitor: Dict,
    heartbeat: Optional[Dict] = None,
) -> Dict:
    """
    Build a notification payload that's expressive enough for every
    rendering style we support.

    Returns a dict with both rendered strings (for plain-text providers)
    and structured primitives (for rich-card renderers like Slack blocks,
    Discord embeds, Teams MessageCards):

        title          str   "BPN went DOWN" (no glyph)
        glyph          str   "🔴"  (status emoji, "" for unknown event)
        text           str   plain multi-line — fine for any channel
        html           str   Telegram-flavoured HTML (b/i/code/a)
        color_hex      str   "#E81123" — Slack/Discord/Teams accent color
        monitor_name   str   "BPN"
        type_label     str   "HTTP" — empty if monitor type isn't set
        url            str   "https://www.bpn.ge/" — empty if not http-ish
        error_msg      str   "Connection refused (504)" — empty when ok/test
        response_ms    int?  None when heartbeat has no ping
        event          str   echoes the input event
    """
    name = (monitor.get("name") or "").strip() or "Monitor"
    type_label = _type_label(monitor.get("type"))
    url = (monitor.get("url") or "").strip()

    if event == "test":
        glyph = STATUS_GLYPH["test"]
        title = "Observer test alert"
    elif event == "down":
        glyph = STATUS_GLYPH["down"]
        title = f"{name} went DOWN"
    elif event == "up":
        glyph = STATUS_GLYPH["up"]
        title = f"{name} {UP_VERB}"
    elif event == "paused":
        glyph = STATUS_GLYPH["paused"]
        title = f"{name} was PAUSED"
    elif event == "resumed":
        glyph = STATUS_GLYPH["resumed"]
        title = f"{name} RESUMED"
    elif event == "slow":
        glyph = STATUS_GLYPH["slow"]
        title = f"{name} responding slowly"
    else:
        glyph = ""
        title = name

    hb = _extract_heartbeat(heartbeat) if event != "test" else {"error_msg": "", "response_ms": None}
    error_msg = hb["error_msg"]
    response_ms = hb["response_ms"]

    body: List[str] = []
    if event == "test":
        body.append(
            "This is a sample notification — real alerts will include the "
            "monitor name, type, response details, and any error message."
        )
    else:
        if type_label and url:
            body.append(f"{type_label} · {url}")
        elif type_label:
            body.append(type_label)
        elif url:
            body.append(url)
        if error_msg:
            body.append(error_msg)
        if response_ms is not None:
            body.append(f"Response: {response_ms}ms")
        # For slow alerts, also surface the threshold so the alert is
        # self-explanatory ("Response: 5234ms (threshold: 1000ms)").
        if event == "slow" and heartbeat:
            threshold_ms = heartbeat.get("threshold_ms")
            if threshold_ms is not None:
                try:
                    body.append(f"Threshold: {int(threshold_ms)}ms")
                except (TypeError, ValueError):
                    pass

    plain_header = f"{glyph} {title}".strip()
    text = "\n".join([plain_header] + body)

    html_header = (
        f"{glyph} <b>{_html_escape(title)}</b>".strip()
        if glyph
        else f"<b>{_html_escape(title)}</b>"
    )
    html_body: List[str] = []
    for ln in body:
        if " · " in ln and ("http://" in ln or "https://" in ln):
            t_part, _, url_part = ln.partition(" · ")
            html_body.append(
                f"<i>{_html_escape(t_part)}</i> · "
                f'<a href="{_html_escape(url_part)}">{_html_escape(url_part)}</a>'
            )
        elif ln.startswith("Response:"):
            _, _, val = ln.partition(": ")
            html_body.append(f"Response: <b>{_html_escape(val)}</b>")
        else:
            html_body.append(_html_escape(ln))
    html = "\n".join([html_header] + html_body)

    return {
        "title": title,
        "glyph": glyph,
        "text": text,
        "html": html,
        "color_hex": _color_for(event),
        "monitor_name": name,
        "type_label": type_label,
        "url": url,
        "error_msg": error_msg,
        "response_ms": response_ms,
        "event": event,
    }
