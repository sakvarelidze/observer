"""Shields.io-style SVG uptime badges.

Self-contained — no `badge-maker` dependency. Hand-rolling keeps the
backend Python-only and the SVG output cache-friendly. The widths use a
6.5px/character approximation that matches Shields.io's defaults closely
enough that badges sit comfortably next to other shields-style badges in
a README without obvious size mismatch.
"""
from __future__ import annotations
from typing import Optional


# Colour bands. Green ≥99%, amber ≥95%, red <95%, grey for "no data".
COLOR_OK = "#4c1"
COLOR_DEGRADED = "#dfb317"
COLOR_DOWN = "#e05d44"
COLOR_UNKNOWN = "#9f9f9f"


def color_for_uptime(uptime: Optional[float]) -> str:
    if uptime is None:
        return COLOR_UNKNOWN
    if uptime >= 99.0:
        return COLOR_OK
    if uptime >= 95.0:
        return COLOR_DEGRADED
    return COLOR_DOWN


def _text_width(text: str) -> int:
    """Approximate the rendered width of `text` in DejaVu Sans 11px.

    Real width depends on font hinting and per-character advance, but the
    Shields convention is a simple average — good enough for badges that
    just need to look balanced. We bias narrow chars (i/l/.) and wide
    chars (W/M) so the box doesn't crop or float.
    """
    width = 0.0
    for ch in text:
        if ch in "ilI.,:;'!|":
            width += 3.0
        elif ch in "WM":
            width += 9.0
        elif ch.isupper() or ch.isdigit():
            width += 7.0
        else:
            width += 6.0
    return int(width + 0.5)


def _xml_escape(s: str) -> str:
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def render_badge(label: str, value: str, color: str) -> str:
    """Compose a Shields.io-flat-style SVG badge."""
    # 10px padding on each side of each segment, like Shields does.
    label_pad = 10
    value_pad = 10
    label_w = _text_width(label) + label_pad * 2
    value_w = _text_width(value) + value_pad * 2
    total = label_w + value_w
    label_x = label_w / 2
    value_x = label_w + value_w / 2

    label_safe = _xml_escape(label)
    value_safe = _xml_escape(value)

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
        f'width="{total}" height="20" role="img" aria-label="{label_safe}: {value_safe}">'
        f'<title>{label_safe}: {value_safe}</title>'
        f'<linearGradient id="s" x2="0" y2="100%">'
        f'<stop offset="0" stop-color="#bbb" stop-opacity=".1"/>'
        f'<stop offset="1" stop-opacity=".1"/>'
        f'</linearGradient>'
        f'<clipPath id="r"><rect width="{total}" height="20" rx="3" fill="#fff"/></clipPath>'
        f'<g clip-path="url(#r)">'
        f'<rect width="{label_w}" height="20" fill="#555"/>'
        f'<rect x="{label_w}" width="{value_w}" height="20" fill="{color}"/>'
        f'<rect width="{total}" height="20" fill="url(#s)"/>'
        f'</g>'
        f'<g fill="#fff" text-anchor="middle" '
        f'font-family="Verdana,Geneva,DejaVu Sans,sans-serif" font-size="11">'
        f'<text x="{label_x}" y="15" fill="#010101" fill-opacity=".3">{label_safe}</text>'
        f'<text x="{label_x}" y="14">{label_safe}</text>'
        f'<text x="{value_x}" y="15" fill="#010101" fill-opacity=".3">{value_safe}</text>'
        f'<text x="{value_x}" y="14">{value_safe}</text>'
        f'</g>'
        f'</svg>'
    )
