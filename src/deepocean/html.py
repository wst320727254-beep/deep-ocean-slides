# -*- coding: utf-8 -*-
"""The HTML / print renderer — a pixel-faithful preview of a Deep Ocean deck.

The renderer draws every page onto a ``1280 x 720 px`` canvas using exactly the
numbers of the style guide (the same ones the PPTX renderer uses): top bar
``y 0-60``, kicker at ``y 80``, page title at ``y 102``, content band
``y 200-640``, footer rule at ``y 680``, page number right-aligned to
``x 1240``, side margins ``40``, gutter ``20``.

Everything is produced as deterministic plain strings — no Jinja2, no
JavaScript, no CDN, no timestamps, no random ids — so the output can be diffed,
cached and asserted on.  Charts are inline SVG built in Python.

Public API
----------
``render(deck, *, standalone=True, title=None)``  full HTML document / fragment
``write(deck, path, **kw)``                       write to disk, return abs path
``render_page(page, deck, index, total)``         one ``<section class="do-page">``
``render_fragment(deck)``                         body markup only (embedding)
``css()``                                         the stylesheet (from tokens)

The stylesheet lives in ``templates/deck.css`` and is loaded through
:mod:`importlib.resources`, with a filesystem fallback, so it works both from a
source checkout and from an installed wheel (``package-data`` covers
``templates/*.css``).  Its ``/* DO_TOKENS */`` marker is replaced at render
time by :func:`deepocean.tokens.css_variables`, which keeps the CSS and the
design tokens from drifting apart.
"""

from __future__ import annotations

import html
import math
import os
import re
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple

from . import schema, tokens

__all__ = ["render", "write", "render_page", "render_fragment", "css",
           "PAGE_W", "PAGE_H", "CONTENT_X", "CONTENT_Y", "CONTENT_W", "CONTENT_H"]

# --------------------------------------------------------------------------- #
# Canvas geometry (px on the 1280x720 design canvas — never invented here)
# --------------------------------------------------------------------------- #

PAGE_W: int = int(tokens.CANVAS["width_px"])            # 1280
PAGE_H: int = int(tokens.CANVAS["height_px"])           # 720
MARGIN: int = int(tokens.SAFE_MARGIN_PX)                # 40
GAP: int = int(tokens.CARD_GAP_PX)                      # 20
CONTENT_X: int = MARGIN                                 # 40
CONTENT_W: int = int(tokens.CONTENT_WIDTH_PX)           # 1200
CONTENT_Y: int = int(tokens.BANDS["content"]["y"])      # 200
CONTENT_H: int = int(tokens.BANDS["content"]["h"])      # 440
FOOTER_Y: int = int(tokens.BANDS["footer"]["y"])        # 680

#: Card height and band bottom — identical to :mod:`deepocean.layouts`.
CARD_H = 440.0
FOOT_Y = 640.0
CONTENT_R = CONTENT_X + CONTENT_W                        # 1240

#: The shared footer is drawn on every page that carries the shared chrome,
#: plus these (chrome-exempt layouts that still leave the footer band free).
_EXTRA_FOOTER_LAYOUTS: Tuple[str, ...] = ("closing",)

_TEMPLATE_MARKER = "/* DO_TOKENS */"
_FONT_MARKER = "/* DO_FONTS */"

#: Generic CSS font keywords that must not be quoted.
_GENERIC_FONTS = ("serif", "sans-serif", "monospace", "cursive", "fantasy",
                  "system-ui", "ui-sans-serif", "ui-serif", "ui-monospace")

# --------------------------------------------------------------------------- #
# Small text utilities (escape early, never emit "None"/"{}")
# --------------------------------------------------------------------------- #

_BULLET_RE = re.compile(r"^\s*(?:[-*•·▪–—])\s+(.+?)\s*$")
_NUMERIC_RE = re.compile(r"^[-−+]?[\d,]+(?:\.\d+)?\s*(?:%|％|px|个|倍)?$")

_NARROW = set("ilI.,:;!|'()[]{}/\\ ")
_WIDE = set("mwMW@%&")


def _esc(value: Any) -> str:
    """HTML-escape any scalar (``None`` becomes an empty string)."""
    if value is None:
        return ""
    return html.escape(str(value), quote=True)


def _lines(text: Any) -> List[str]:
    return str(text).replace("\r\n", "\n").replace("\r", "\n").split("\n")


def _inline(text: Any) -> str:
    """Escape a single-line string; ``\\n`` becomes ``<br>``."""
    if text is None:
        return ""
    if isinstance(text, (dict, list, tuple)):
        text = _plain(text)
    return "<br>".join(_esc(line) for line in _lines(text) if line.strip()) or _esc("")


def _rich(text: Any) -> str:
    """Escape body copy, turning ``\\n`` into paragraphs and ``- `` into a list."""
    if text is None:
        return ""
    if isinstance(text, (dict, list, tuple)):
        text = _plain(text)
    out: List[str] = []
    bullets: List[str] = []

    def flush() -> None:
        if bullets:
            out.append('<ul class="do-items is-tight">'
                       + "".join(f"<li>{_esc(b)}</li>" for b in bullets)
                       + "</ul>")
            bullets.clear()

    for raw in _lines(text):
        line = raw.strip()
        if not line:
            flush()
            continue
        match = _BULLET_RE.match(line)
        if match:
            bullets.append(match.group(1))
            continue
        flush()
        out.append(f"<p>{_esc(line)}</p>")
    flush()
    return "".join(out)


def _items_html(items: Any, cls: str = "do-items") -> str:
    """Render a bullet list from strings, ``(lead, text)`` pairs or dicts."""
    if items is None:
        return ""
    if isinstance(items, (str, dict)):
        items = [items]
    lis: List[str] = []
    for item in items:
        if isinstance(item, dict):
            lead = _esc(_plain(item.get("lead")))
            text = item.get("text")
            if text is None:
                text = item.get("body", "")
            inner = (f'<b class="do-lead">{lead}</b> ' if lead else "") + _inline(text)
        elif isinstance(item, (list, tuple)) and len(item) == 2:
            inner = f'<b class="do-lead">{_esc(_plain(item[0]))}</b> {_inline(item[1])}'
        else:
            inner = _inline(item)
        if inner.strip():
            lis.append(f"<li>{inner}</li>")
    if not lis:
        return ""
    return f'<ul class="{cls}">' + "".join(lis) + "</ul>"


def _plain(value: Any) -> str:
    """Flatten any leftover layout value into readable text (fallback renderer)."""
    if value is None:
        return ""
    if isinstance(value, dict):
        return "；".join(f"{k}：{_plain(v)}" for k, v in value.items() if _plain(v))
    if isinstance(value, (list, tuple)):
        return " · ".join(_plain(v) for v in value if _plain(v))
    if isinstance(value, bool):
        return "是" if value else "否"
    return str(value)


# --------------------------------------------------------------------------- #
# Number helpers (deterministic formatting: 12.0 -> "12", 0.50 -> "0.5")
# --------------------------------------------------------------------------- #


def _px(value: Any) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    if abs(number - round(number)) < 1e-6:
        return str(int(round(number)))
    return ("%.2f" % number).rstrip("0").rstrip(".")


def _num(value: Any) -> str:
    """Format a chart number for a data label."""
    if isinstance(value, str):
        return value
    return _px(value)


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _as_int(value: Any, default: int = 0) -> int:
    try:
        return int(round(float(value)))
    except (TypeError, ValueError):
        return default


def _clamp(value: float, low: float, high: float) -> float:
    if high < low:
        high = low
    return max(low, min(high, value))


def _round(value: float) -> int:
    return int(round(value))


def _text_width(text: str, size: float, bold: bool = False) -> float:
    """Rough rendered width in px (CJK = 1em, narrow Latin ~0.3em)."""
    factor = 1.06 if bold else 1.0
    total = 0.0
    for ch in str(text):
        code = ord(ch)
        if code > 0x2E7F:
            total += size * factor
        elif ch in _NARROW:
            total += size * 0.30 * factor
        elif ch in _WIDE:
            total += size * 0.95 * factor
        else:
            total += size * 0.55 * factor
    return total


def _units(text: str) -> Iterable[str]:
    word = ""
    for ch in str(text):
        if ch == "\n":
            if word:
                yield word
                word = ""
            continue
        if ord(ch) > 0x2E7F or ch in _NARROW or ch in _WIDE:
            if word:
                yield word
                word = ""
            yield ch
        else:
            word += ch
    if word:
        yield word


def _wrap_count(text: Any, size: float, width: float, bold: bool = False) -> int:
    """How many lines ``text`` occupies at ``size`` px inside ``width`` px."""
    if text is None or str(text) == "":
        return 1
    lines, current = 1, 0.0
    for unit in _units(str(text)):
        unit_w = _text_width(unit, size, bold)
        if unit_w > width:
            lines += int(unit_w // max(1.0, width))
            current = unit_w % max(1.0, width)
            continue
        if current and current + unit_w > width:
            lines += 1
            current = unit_w
        else:
            current += unit_w
    return lines


def _truncate(text: Any, size: float, width: float, bold: bool = False,
              ellipsis: str = "…") -> str:
    text = "" if text is None else str(text)
    if _text_width(text, size, bold) <= width:
        return text
    out = ""
    for ch in text:
        if _text_width(out + ch + ellipsis, size, bold) > width:
            break
        out += ch
    return (out + ellipsis) if out else ellipsis


def _looks_numeric(text: Any) -> bool:
    return bool(_NUMERIC_RE.match(str(text).strip())) if text is not None else False


# --------------------------------------------------------------------------- #
# Colour / tone resolution
# --------------------------------------------------------------------------- #

_CARD_TONES = tuple(schema.TONES)               # plain tint primary accent neutral danger alert

_TONE_CLASS: Dict[str, str] = {
    "plain": "do-tone-plain",
    "tint": "do-tone-tint",
    "accent": "do-tone-accent",
    "neutral": "do-tone-neutral",
    "danger": "do-tone-danger",
    "alert": "do-tone-alert",
    "primary": "do-tone-primary",
}

_TONE_ACCENT: Dict[str, str] = {
    "plain": "teal", "tint": "teal", "accent": "teal", "neutral": "grayblue",
    "danger": "brick", "alert": "brick", "primary": "teal",
}

_VALUE_TONES: Dict[str, str] = {
    "up": "do-u-teal", "teal": "do-u-teal", "positive": "do-u-teal", "accent": "do-u-teal",
    "down": "do-u-brick", "brick": "do-u-brick", "danger": "do-u-brick",
    "negative": "do-u-brick", "alert": "do-u-brick", "substitution": "do-u-brick",
    "neutral": "do-u-navy", "navy": "do-u-navy", "primary": "do-u-navy",
    "flat": "do-u-navy", "complementary": "do-u-teal",
    "grayblue": "do-u-grayblue", "null": "do-u-grayblue", "muted": "do-u-grayblue",
}


def _hex(value: Any, fallback: str = "navy") -> str:
    """Resolve a palette key / role / ``#hex`` to ``#RRGGBB`` (never raises)."""
    if value is None or str(value).strip() == "":
        key = fallback
    else:
        key = str(value).strip()
    try:
        return tokens.hex_of(key)
    except (KeyError, TypeError, ValueError):
        return tokens.hex_of(fallback)


def _tone_class(tone: Any, default: str = "plain") -> str:
    key = str(tone or "").strip().lower()
    if key not in _TONE_CLASS:
        key = default if default in _TONE_CLASS else "plain"
    return _TONE_CLASS[key]


def _split_tone(tone: Any) -> Tuple[str, str]:
    """``tone`` -> ``(card_tone, value_tone)``; surface tones also tint the card."""
    key = str(tone or "").strip().lower()
    if key in _CARD_TONES:
        return key, key
    return "", key


def _value_class(tone: Any) -> str:
    return _VALUE_TONES.get(str(tone or "").strip().lower(), "")


def _chip_class(tone: Any) -> str:
    key = str(tone or "").strip().lower()
    if key in ("danger", "alert", "down", "brick", "negative"):
        return "do-chip is-danger"
    if key in ("neutral", "grayblue", "null", "muted"):
        return "do-chip is-neutral"
    return "do-chip"


# --------------------------------------------------------------------------- #
# Markup building blocks
# --------------------------------------------------------------------------- #


def _box(x: float, y: float, w: float, h: float) -> str:
    """Inline px geometry — the same numbers the PPTX renderer positions with."""
    return (f"left:{_px(x)}px;top:{_px(y)}px;"
            f"width:{_px(max(0.0, w))}px;height:{_px(max(0.0, h))}px;")


def _card(box_style: str, inner: str, *, tone: Any = "plain", accent: Any = None,
          accent_side: str = "left", pad: str = "md", border_accent: bool = False,
          extra: str = "") -> str:
    classes = ["do-card", _tone_class(tone)]
    if pad == "sm":
        classes.append("is-pad-sm")
    elif pad == "lg":
        classes.append("is-pad-lg")
    style = box_style
    if accent:
        accent_hex = _hex(accent, _TONE_ACCENT.get(str(tone or "plain").lower(), "teal"))
        classes.append("has-accent-left" if accent_side == "left" else "has-accent-top")
        style += f"--do-accent:{accent_hex};"
    if border_accent:
        accent_hex = _hex(accent or "teal")
        classes.append("has-border-accent")
        style += f"--do-accent:{accent_hex};"
    if extra:
        classes.append(extra)
    return f'<div class="{" ".join(classes)}" style="{style}">{inner}</div>'


def _inner(*, chip: Any = None, chip_en: Any = None, chip_tone: Any = None,
           kicker: Any = None, title: Any = None, title_sm: bool = False,
           label: Any = None, value: Any = None, unit: Any = None,
           value_class: str = "", value_tone: Any = None, note: Any = None,
           body: Any = None, body_sm: bool = False, items: Any = None,
           footer: Any = None, title_tag: str = "h3") -> str:
    """The five-part card skeleton: S1 head, S2 title, S3 value/body, S4 anchors."""
    parts: List[str] = []
    if chip or chip_en:
        bits = []
        if chip:
            bits.append(f'<span class="{_chip_class(chip_tone)}">{_esc(chip)}</span>')
        if chip_en:
            bits.append(f'<span class="do-chip-en">{_esc(chip_en)}</span>')
        parts.append('<div class="do-card-head">' + "".join(bits) + "</div>")
    if kicker is not None and str(kicker).strip():
        parts.append(f'<p class="do-label">{_inline(kicker)}</p>')
    if title is not None and str(title).strip():
        cls = "do-card-title is-sm" if title_sm else "do-card-title"
        parts.append(f'<{title_tag} class="{cls}">{_inline(title)}</{title_tag}>')
    if label is not None and str(label).strip():
        parts.append(f'<p class="do-label">{_inline(label)}</p>')
    if value is not None and str(value).strip() != "":
        cls = "do-kpi-value"
        if value_class:
            cls += f" {value_class}"
        tone_cls = _value_class(value_tone)
        if tone_cls:
            cls += f" {tone_cls}"
        unit_html = f'<span class="do-unit">{_esc(unit)}</span>' if unit else ""
        parts.append(f'<p class="{cls}">{_inline(value)}{unit_html}</p>')
    if note is not None and str(note).strip():
        parts.append(f'<p class="do-kpi-note">{_inline(note)}</p>')
    if body is not None and str(body).strip():
        cls = "do-body is-sm" if body_sm else "do-body"
        parts.append(f'<div class="{cls}">{_rich(body)}</div>')
    items_html = _items_html(items)
    if items_html:
        parts.append(items_html)
    if footer is not None and str(footer).strip():
        parts.append(f'<div class="do-card-foot">{_inline(footer)}</div>')
    return "".join(parts)


def _card_from_dict(x: float, y: float, w: float, h: float, data: Any, *,
                    default_tone: Any = "plain", accent: Any = None,
                    accent_side: str = "left", pad: str = "md",
                    title_sm: bool = False, value_class: str = "",
                    border_accent: bool = False, chip_tone: Any = None,
                    body_sm: bool = False) -> str:
    """Render a schema-style card dict; anything unusable degrades to empty."""
    if isinstance(data, dict):
        card = data
    elif data is None:
        card = {}
    else:
        card = {"body": data}
    card_tone, value_tone = _split_tone(card.get("tone"))
    inner = _inner(
        chip=card.get("chip"), chip_en=card.get("chip_en"),
        chip_tone=card.get("chip_tone") or chip_tone,
        kicker=card.get("kicker"),
        title=card.get("title"), title_sm=title_sm,
        label=card.get("label"), value=card.get("value"), unit=card.get("unit"),
        value_class=value_class or card.get("value_class", ""),
        value_tone=card.get("value_tone") or value_tone,
        note=card.get("note"), body=card.get("body"), body_sm=body_sm,
        items=card.get("items"), footer=card.get("footer"),
    )
    return _card(_box(x, y, w, h), inner, tone=card_tone or default_tone,
                 accent=accent or card.get("accent"), accent_side=accent_side,
                 pad=pad, border_accent=border_accent)


# --------------------------------------------------------------------------- #
# Charts — inline SVG, generated in Python, no JavaScript and no CDN
# --------------------------------------------------------------------------- #

_CHART_KINDS = {
    "bar": "bar", "column": "bar", "columnchart": "bar", "barchart": "bar",
    "clustered": "bar", "grouped": "bar",
    "line": "line", "linechart": "line", "trend": "line",
    "doughnut": "doughnut", "donut": "doughnut", "pie": "doughnut",
    "doughnutchart": "doughnut", "ring": "doughnut",
}


def _chart_kind(value: Any) -> str:
    key = str(value or tokens.CHART["default_type"]).strip().lower().replace("-", "").replace("_", "")
    return _CHART_KINDS.get(key, "bar")


def _series_color(value: Any, index: int = 0) -> str:
    palette = list(tokens.CHART["series_colors"])
    fallback = palette[index % len(palette)]
    if value is None or str(value).strip() == "":
        return _hex(fallback)
    return _hex(value, fallback)


def _chart_series(chart: Dict[str, Any]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    raw_series = chart.get("series")
    if not isinstance(raw_series, (list, tuple)):
        raw_series = []
    for index, item in enumerate(raw_series):
        if not isinstance(item, dict):
            continue
        values = item.get("values")
        if not isinstance(values, (list, tuple)) or not values:
            continue
        out.append({
            "name": _plain(item.get("name")),
            "values": list(values),
            "floats": [_as_float(v, 0.0) for v in values],
            "color": _series_color(item.get("color"), index),
        })
    return out


def _empty_chart(width: float, height: float, message: str = "暂无数据") -> str:
    return (
        f'<rect class="do-chart-empty" x="0.5" y="0.5" width="{_px(max(1.0, width - 1))}" '
        f'height="{_px(max(1.0, height - 1))}" rx="6"/>'
        f'<text class="do-cat" x="{_px(width / 2)}" y="{_px(height / 2)}" '
        f'text-anchor="middle" dy=".34em">{_esc(message)}</text>'
    )


def _svg(width: float, height: float, body: str, label: str = "图表") -> str:
    return (
        f'<svg class="do-chart" xmlns="http://www.w3.org/2000/svg" role="img" '
        f'aria-label="{_esc(label)}" width="{_px(width)}" height="{_px(height)}" '
        f'viewBox="0 0 {_px(width)} {_px(height)}">{body}</svg>'
    )


def _legend_svg(series: Sequence[Dict[str, Any]], x_left: float, x_right: float,
                y: float) -> str:
    """Right-aligned legend row; names are truncated instead of overflowing."""
    named = [s for s in series if s.get("name")]
    if not named or x_right <= x_left:
        return ""
    size = 11.5
    gaps = 14.0 * (len(named) - 1)
    avail = max(0.0, (x_right - x_left) - gaps)
    share = avail / len(named)
    parts: List[str] = []
    x = x_left
    for item in named:
        name = _truncate(item["name"], size, max(6.0, share - 20.0), True)
        width = _text_width(name, size, True) + 20.0
        parts.append(f'<rect x="{_px(x)}" y="{_px(y + 1)}" width="10" height="10" rx="2" '
                     f'fill="{item["color"]}"/>')
        parts.append(f'<text class="do-legend" x="{_px(x + 15)}" y="{_px(y + 11)}">{_esc(name)}</text>')
        x += width + 14.0
    return "".join(parts)


def _nice_step(raw: float) -> float:
    """A human-friendly axis step (1 / 2 / 2.5 / 5 / 10 x 10^k)."""
    if raw <= 0:
        return 1.0
    exponent = math.floor(math.log10(raw))
    base = 10.0 ** exponent
    for multiple in (1.0, 2.0, 2.5, 5.0, 10.0):
        if raw <= multiple * base:
            return multiple * base
    return 10.0 * base


def _axis_bounds(values: Sequence[float]) -> Tuple[float, float, List[float]]:
    """Nice lo/hi bounds + tick values; always includes 0 and leaves label room."""
    lo = min(0.0, min(values))
    hi = max(0.0, max(values))
    span = hi - lo
    if span < 1e-9:
        span = abs(hi) or 1.0
    step = _nice_step(span / 4.0)
    lo_b = math.floor(lo / step) * step
    hi_b = math.ceil(hi / step) * step
    while (hi_b - lo_b) / step > 7:                      # never more than 7 ticks
        step *= 2.0
        lo_b = math.floor(lo / step) * step
        hi_b = math.ceil(hi / step) * step
    if hi_b - lo_b < 1e-9:
        hi_b = lo_b + step
    ticks: List[float] = []
    value = lo_b
    guard = 0
    while value <= hi_b + step / 2.0 and guard < 40:
        ticks.append(round(value, 6))
        value += step
        guard += 1
    return lo_b, hi_b, ticks


def _axis_label(value: float, step: float) -> str:
    if abs(value - round(value)) < 1e-9 and abs(step) >= 1:
        return _num(int(round(value)))
    if abs(step) >= 1:
        return _num(round(value, 1))
    if abs(step) >= 0.1:
        return _num(round(value, 2))
    return _num(round(value, 3))


def _xy_chart(kind: str, series: List[Dict[str, Any]], cats: List[str],
              width: float, height: float) -> str:
    """Grouped bar chart or multi-series line chart on shared axes."""
    if not cats:
        longest = max(len(s["values"]) for s in series)
        cats = [str(i + 1) for i in range(longest)]
    pad_l = _clamp(width * 0.09, 30.0, 56.0)
    pad_r = 14.0
    pad_t = 42.0
    pad_b = _clamp(height * 0.15, 30.0, 50.0)
    x0, x1 = pad_l, width - pad_r
    y0, y1 = pad_t, height - pad_b
    if x1 - x0 < 60.0 or y1 - y0 < 50.0:
        return _empty_chart(width, height)

    all_values = [v for s in series for v in s["floats"]]
    if not all_values:
        return _empty_chart(width, height)
    ymin, ymax, ticks = _axis_bounds(all_values)
    step = ticks[1] - ticks[0] if len(ticks) > 1 else 1.0

    def scale_y(value: float) -> float:
        return y1 - (value - ymin) / (ymax - ymin) * (y1 - y0)

    parts: List[str] = []
    parts.append(_legend_svg(series, x0, x1, 6.0))

    # y ticks (no gridlines — the guide forbids them)
    for value in ticks:
        y = scale_y(value)
        parts.append(f'<text class="do-tick" x="{_px(x0 - 8)}" y="{_px(y)}" '
                     f'text-anchor="end" dy=".32em">{_esc(_axis_label(value, step))}</text>')
    parts.append(f'<line class="do-axis" x1="{_px(x0)}" y1="{_px(y0)}" '
                 f'x2="{_px(x0)}" y2="{_px(y1)}"/>')
    zero_y = scale_y(0.0)
    parts.append(f'<line class="do-axis" x1="{_px(x0)}" y1="{_px(zero_y)}" '
                 f'x2="{_px(x1)}" y2="{_px(zero_y)}"/>')

    count = max(1, len(cats))
    group_w = (x1 - x0) / count
    label_size = 11.5 if group_w >= 46.0 else 10.0

    if kind == "line":
        for item in series:
            points = []
            for index, value in enumerate(item["floats"]):
                cx = x0 + (index + 0.5) * group_w
                points.append((cx, scale_y(value)))
            if len(points) >= 2:
                path = " ".join(f"{_px(px)},{_px(py)}" for px, py in points)
                parts.append(f'<polyline class="do-line" points="{path}" '
                             f'stroke="{item["color"]}"/>')
            for index, (cx, cy) in enumerate(points):
                parts.append(f'<circle class="do-point" cx="{_px(cx)}" cy="{_px(cy)}" r="3.2" '
                             f'stroke="{item["color"]}"/>')
                raw = item["values"][index] if index < len(item["values"]) else ""
                vy = cy - 8 if item["floats"][index] >= 0 else cy + 15
                cls = "do-val" if count <= 8 else "do-val is-sm"
                parts.append(f'<text class="{cls}" x="{_px(cx)}" y="{_px(vy)}" '
                             f'text-anchor="middle">{_esc(_num(raw))}</text>')
    else:
        series_count = max(1, len(series))
        bar_w = min(46.0, (group_w * 0.72) / series_count)
        for index in range(count):
            group_center = x0 + (index + 0.5) * group_w
            start = group_center - (series_count * bar_w) / 2.0
            for si, item in enumerate(series):
                if index >= len(item["floats"]):
                    continue
                value = item["floats"][index]
                top = min(scale_y(value), zero_y)
                bar_h = abs(scale_y(value) - zero_y)
                bx = start + si * bar_w
                parts.append(f'<rect x="{_px(bx)}" y="{_px(top)}" width="{_px(max(1.0, bar_w - 2))}" '
                             f'height="{_px(max(1.0, bar_h))}" rx="2" fill="{item["color"]}"/>')
                raw = item["values"][index] if index < len(item["values"]) else ""
                vy = top - 6 if value >= 0 else top + bar_h + 13
                cls = "do-val" if series_count <= 2 else "do-val is-sm"
                parts.append(f'<text class="{cls}" x="{_px(bx + (bar_w - 2) / 2)}" y="{_px(vy)}" '
                             f'text-anchor="middle">{_esc(_num(raw))}</text>')
            text = _truncate(cats[index] if index < len(cats) else "", label_size,
                             max(18.0, group_w - 6.0))
            parts.append(f'<text class="do-cat" x="{_px(group_center)}" y="{_px(y1 + 18)}" '
                         f'text-anchor="middle" font-size="{_px(label_size)}">{_esc(text)}</text>')
    return "".join(parts)


def _polar(cx: float, cy: float, radius: float, angle_deg: float) -> Tuple[float, float]:
    """Point on a circle; 0 degrees is 12 o'clock, clockwise."""
    angle = math.radians(angle_deg - 90.0)
    return cx + radius * math.cos(angle), cy + radius * math.sin(angle)


def _ring_arc(cx: float, cy: float, r_out: float, r_in: float,
              start_deg: float, end_deg: float) -> str:
    """One doughnut segment as a filled SVG arc path."""
    large = 1 if (end_deg - start_deg) > 180.0 else 0
    x0o, y0o = _polar(cx, cy, r_out, start_deg)
    x1o, y1o = _polar(cx, cy, r_out, end_deg)
    x1i, y1i = _polar(cx, cy, r_in, end_deg)
    x0i, y0i = _polar(cx, cy, r_in, start_deg)
    return (f"M{_px(x0o)},{_px(y0o)} "
            f"A{_px(r_out)},{_px(r_out)} 0 {large} 1 {_px(x1o)},{_px(y1o)} "
            f"L{_px(x1i)},{_px(y1i)} "
            f"A{_px(r_in)},{_px(r_in)} 0 {large} 0 {_px(x0i)},{_px(y0i)} Z")


def _doughnut_chart(series: List[Dict[str, Any]], cats: List[str],
                    width: float, height: float, chart: Dict[str, Any],
                    label: str) -> str:
    """Ring chart as SVG arc segments, with a centre label and a side legend."""
    if len(series) > 1 and all(len(s["values"]) == 1 for s in series):
        slices = [{"name": s["name"] or (cats[i] if i < len(cats) else ""),
                   "value": s["values"][0], "number": s["floats"][0], "color": s["color"]}
                  for i, s in enumerate(series)]
    else:
        first = series[0]
        slices = []
        for i, value in enumerate(first["values"]):
            slices.append({"name": cats[i] if i < len(cats) else str(i + 1),
                           "value": value, "number": first["floats"][i],
                           "color": _series_color(None, i)})
    slices = [s for s in slices if s["number"] > 0]
    if not slices:
        return _empty_chart(width, height)
    if len(slices) > 8:                                  # keep the legend readable
        head, tail = slices[:7], slices[7:]
        head.append({"name": "其他", "value": sum(s["number"] for s in tail),
                     "number": sum(s["number"] for s in tail),
                     "color": _hex("grayblue")})
        slices = head

    total = sum(s["number"] for s in slices) or 1.0
    legend_w = min(width * 0.5, 300.0)
    ring_area = max(80.0, width - legend_w)
    radius = max(26.0, min(ring_area / 2.0 - 16.0, height / 2.0 - 14.0))
    thickness = max(12.0, radius * 0.36)
    cx, cy = ring_area / 2.0, height / 2.0

    parts: List[str] = []
    radius_in = max(6.0, radius - thickness)
    parts.append(f'<circle cx="{_px(cx)}" cy="{_px(cy)}" r="{_px(radius)}" fill="{_hex("light")}"/>')
    angle = 0.0
    for item in slices:
        share = item["number"] / total
        sweep = share * 360.0
        if sweep >= 359.5:                              # a single full ring
            parts.append(f'<circle cx="{_px(cx)}" cy="{_px(cy)}" r="{_px(radius)}" '
                         f'fill="{item["color"]}"/>')
            parts.append(f'<circle cx="{_px(cx)}" cy="{_px(cy)}" r="{_px(radius_in)}" '
                         f'fill="{_hex("white")}"/>')
        else:
            gap = 1.2 if sweep > 6.0 else 0.0
            parts.append(f'<path d="{_ring_arc(cx, cy, radius, radius_in, angle + gap / 2, angle + sweep - gap / 2)}" '
                         f'fill="{item["color"]}"/>')
        angle += sweep

    centre_value = chart.get("center") if isinstance(chart, dict) else None
    if centre_value is None or str(centre_value).strip() == "":
        centre_value = _num(round(total, 2))
        centre_label = chart.get("center_label") or chart.get("unit") or "合计"
    else:
        centre_label = chart.get("center_label") or ""
    parts.append(f'<text class="do-center-v" x="{_px(cx)}" y="{_px(cy + 2)}" '
                 f'text-anchor="middle" dy=".10em">{_esc(centre_value)}</text>')
    if centre_label:
        parts.append(f'<text class="do-center-l" x="{_px(cx)}" y="{_px(cy + 22)}" '
                     f'text-anchor="middle">{_esc(centre_label)}</text>')

    row_h = _clamp((height - 16.0) / max(1, len(slices)), 16.0, 26.0)
    legend_x = ring_area + 4.0
    start_y = max(6.0, (height - row_h * len(slices)) / 2.0)
    for index, item in enumerate(slices):
        y = start_y + index * row_h
        share = item["number"] / total * 100.0
        share_text = f"{share:.1f}%" if abs(share - round(share)) > 0.05 else f"{share:.0f}%"
        name = _truncate(item["name"], 11.5, max(30.0, legend_w - 96.0))
        parts.append(f'<rect x="{_px(legend_x)}" y="{_px(y + row_h / 2 - 5)}" width="10" height="10" '
                     f'rx="2" fill="{item["color"]}"/>')
        parts.append(f'<text class="do-legend" x="{_px(legend_x + 15)}" y="{_px(y + row_h / 2 + 4)}">'
                     f'{_esc(name)}</text>')
        parts.append(f'<text class="do-val" x="{_px(width - 2)}" y="{_px(y + row_h / 2 + 4)}" '
                     f'text-anchor="end">{_esc(_num(item["value"]))} · {_esc(share_text)}</text>')
    return "".join(parts)


def chart_svg(chart: Any, width: float, height: float) -> str:
    """Render a ``chart_insight.chart`` dict as inline SVG (bar / line / doughnut)."""
    chart = chart if isinstance(chart, dict) else {}
    kind = _chart_kind(chart.get("type"))
    cats = [_plain(c) for c in (chart.get("categories") or [])]
    series = _chart_series(chart)
    label = _plain(chart.get("title")) or "图表"
    if not series:
        return _svg(width, height, _empty_chart(width, height, _plain(chart.get("note")) or "暂无数据"), label)
    if kind == "doughnut":
        body = _doughnut_chart(series, cats, width, height, chart, label)
    else:
        body = _xy_chart(kind, series, cats, width, height)
    return _svg(width, height, body, label)


# --------------------------------------------------------------------------- #
# Shared chrome (bands A, B, D)
# --------------------------------------------------------------------------- #


def _topbar(deck: Any, page: Any, tall: bool = False, show_series: bool = True) -> str:
    series = ""
    if isinstance(getattr(page, "data", None), dict):
        series = page.data.get("series") or ""
    if not series:
        series = getattr(deck.meta, "journal", "") or ""
    classes = "do-topbar is-tall" if tall else "do-topbar"
    tag = f'<span class="do-series">{_esc(series)}</span>' if (series and show_series) else ""
    return f'<div class="{classes}" aria-hidden="true"><span class="do-mark"></span>{tag}</div>'


def _title_block(page: Any) -> str:
    parts = ['<div class="do-titleblock">']
    if page.kicker:
        parts.append(f'<p class="do-kicker">{_inline(page.kicker)}</p>')
    title = page.title or ""
    if title:
        cls = "do-title"
        length = len(title)
        if length > 42:
            cls += " is-xlong"
        elif length > 30:
            cls += " is-long"
        parts.append(f'<h2 class="{cls}">{_inline(title)}</h2>')
    sub_bits: List[str] = []
    for bit in (page.subtitle, page.title_en):
        if bit and bit not in sub_bits:
            sub_bits.append(bit)
    if sub_bits:
        parts.append(f'<p class="do-subtitle">{_inline(" · ".join(sub_bits))}</p>')
    parts.append("</div>")
    return "".join(parts)


def _page_number(index: int, total: int) -> str:
    width = max(2, len(str(max(1, total))))
    return f"{index:0{width}d} / {total:0{width}d}"


def _footer(deck: Any, index: int, total: int) -> str:
    note = ""
    try:
        note = deck.resolved_footer_note()
    except (AttributeError, TypeError):
        note = ""
    parts = ['<footer class="do-footer">']
    if note:
        parts.append(f'<div class="do-footer-note">{_inline(note)}</div>')
    parts.append(f'<div class="do-page-number">{_esc(_page_number(index, total))}</div>')
    parts.append("</footer>")
    return "".join(parts)


# --------------------------------------------------------------------------- #
# Layouts 01-12  (each one consumes exactly the fields of schema.LAYOUTS)
# --------------------------------------------------------------------------- #


def _layout_cover(page: Any, deck: Any, index: int, total: int) -> str:
    """Cover: band-free (chrome-exempt), mirrors ``layouts.render_cover``."""
    data = page.data if isinstance(page.data, dict) else {}
    meta = deck.meta
    title = page.title or meta.title
    english = (page.title_en or data.get("english_title") or page.subtitle
               or meta.subtitle)
    authors = data.get("authors") or " · ".join(meta.authors)
    affiliation = data.get("affiliation") or meta.affiliation
    series = data.get("series") or meta.journal
    note = data.get("note") or meta.source_note
    band = data.get("band")
    kicker = page.kicker or meta.kicker

    out = [_topbar(deck, page)]
    out.append('<div class="do-cover-rule"></div>')

    y = 140.0
    if kicker:
        out.append(f'<p class="do-cover-kicker">{_esc(kicker)}</p>')
        y += 26.0
    size = 44.0
    while size > 30.0 and _wrap_count(title, size, 1100.0, True) > 2:
        size -= 2.0
    cls = "do-cover-title" + (" is-long" if size <= 38 else "") + (" is-xlong" if size <= 33 else "")
    title_lines = _wrap_count(title, size, 1100.0, True) if title else 1
    out.append(f'<h1 class="{cls}" style="top:{_px(y)}px;font-size:{_px(size)}px;">'
               f'{_inline(title)}</h1>')
    y += title_lines * size * 1.22 + 12.0
    if english:
        english_lines = _wrap_count(english, 26.0, 1100.0)
        out.append(f'<p class="do-cover-en" style="top:{_px(y)}px;">{_inline(english)}</p>')
        y += english_lines * 26.0 * 1.3 + 10.0
    out.append('<div class="do-cover-divider"></div>')
    info_y = max(440.0, y + 14.0)
    if authors:
        out.append(f'<p class="do-cover-authors" style="top:{_px(info_y)}px;">{_inline(authors)}</p>')
    if affiliation:
        out.append(f'<p class="do-cover-meta" style="top:{_px(info_y + 26.0)}px;">'
                   f'{_inline(affiliation)}</p>')

    out.append('<div class="do-cover-strip"></div>')
    out.append('<div class="do-cover-stripbar"></div>')
    if note:
        out.append(f'<p class="do-cover-note">{_inline(note)}</p>')
    out.append(f'<p class="do-cover-pagenum">{_esc(_page_number(index, total))}</p>')
    if band:
        out.append(f'<p class="do-cover-band">{_inline(band)}</p>')
    out.append('<div class="do-cover-bottom"></div>')
    return "\n".join(out)


def _layout_two_column(page: Any, deck: Any, index: int, total: int) -> str:
    data = page.data if isinstance(page.data, dict) else {}
    left = data.get("left") or {}
    right = data.get("right") or []
    if isinstance(right, dict):
        right = [right]
    elif not isinstance(right, (list, tuple)):
        right = []
    ratio = _clamp(_as_float(data.get("ratio"), 0.60), 0.50, 0.70)
    height = CARD_H
    left_w = (CONTENT_W - GAP) * ratio
    right_x = CONTENT_X + left_w + GAP
    right_w = CONTENT_R - right_x

    out = [_card_from_dict(CONTENT_X, CONTENT_Y, left_w, height, left,
                           default_tone="tint", accent="teal", accent_side="left",
                           pad="md")]
    cards: List[Any] = list(right) or [{}]
    count = len(cards)
    card_h = (height - GAP * (count - 1)) / count
    for i, card in enumerate(cards):
        y = CONTENT_Y + i * (card_h + GAP)
        default_tone = "primary" if i == count - 1 else "plain"
        out.append(_card_from_dict(right_x, y, right_w, card_h, card,
                                   default_tone=default_tone, title_sm=True, pad="sm",
                                   body_sm=card_h < 116))
    return "\n".join(out)


def _number_card(x: float, y: float, w: float, h: float, item: Any,
                 value_class: str, hero: bool, pad: str = "md") -> str:
    item = item if isinstance(item, dict) else {"number": item}
    tone, value_tone = _split_tone(item.get("tone"))
    if hero:
        inner = _inner(label=item.get("title"), value=item.get("number"),
                       unit=item.get("unit"), value_class=value_class,
                       value_tone=value_tone, note=item.get("note"),
                       body=item.get("body"), items=item.get("items"),
                       footer=item.get("footer"))
    else:
        inner = _inner(title=item.get("title"), title_sm=True,
                       value=item.get("number"), unit=item.get("unit"),
                       value_class=value_class, value_tone=value_tone,
                       note=item.get("note"), body=item.get("body"),
                       body_sm=True, items=item.get("items"),
                       footer=item.get("footer"))
    return _card(_box(x, y, w, h), inner, tone=tone or ("plain" if hero else "tint"),
                 pad=pad)


def _layout_big_number(page: Any, deck: Any, index: int, total: int) -> str:
    data = page.data if isinstance(page.data, dict) else {}
    items = [it for it in (data.get("items") or []) if it is not None]
    mode = str(data.get("mode") or "hero").strip().lower()
    height = CARD_H
    if not items:
        return _card(_box(CONTENT_X, CONTENT_Y, CONTENT_W, height),
                     _inner(title=page.title, body="（本页暂无数据）"),
                     tone="tint", pad="md")
    if mode == "grid" or len(items) == 1:
        count = len(items)
        card_w = (CONTENT_W - GAP * (count - 1)) / count
        value_class = "is-lg" if count <= 2 else ("is-md" if count == 3 else "is-sm")
        return "\n".join(
            _number_card(CONTENT_X + i * (card_w + GAP), CONTENT_Y, card_w, height,
                         item, value_class, hero=True)
            for i, item in enumerate(items))
    # hero: one 580px anchor card plus 200/210px cards (guide section 06)
    big_w = 580.0
    out = [_number_card(CONTENT_X, CONTENT_Y, big_w, height, items[0], "is-lg",
                        hero=True, pad="md")]
    rest = items[1:]
    right_x = CONTENT_X + big_w + GAP
    right_w = CONTENT_R - right_x
    heights = [200.0, 210.0] if len(rest) == 2 else None
    if heights is None:
        count = len(rest)
        heights = [(height - GAP * (count - 1)) / count] * count
    y = CONTENT_Y
    for i, item in enumerate(rest):
        card_h = heights[i] if i < len(heights) else heights[-1]
        out.append(_number_card(right_x, y, right_w, card_h, item, "is-md", hero=False))
        y += card_h + GAP
    return "\n".join(out)


def _layout_experiment_design(page: Any, deck: Any, index: int, total: int) -> str:
    data = page.data if isinstance(page.data, dict) else {}
    steps = [s for s in (data.get("steps") or []) if s is not None]
    groups = data.get("groups") or {}
    if not isinstance(groups, dict):
        groups = {}
    vs = _plain(data.get("vs")) or "VS"
    verdict = data.get("verdict")

    out: List[str] = []
    has_pair = bool(groups.get("left") or groups.get("right") or verdict)
    flow_h = 124.0 if has_pair else CARD_H
    if steps:
        count = len(steps)
        arrow_gap = 24.0
        node_w = max(80.0, (CONTENT_W - (count - 1) * arrow_gap) / count)
        node_h = min(60.0, flow_h)
        node_y = CONTENT_Y + (flow_h - node_h) / 2.0
        for i, step in enumerate(steps):
            step = step if isinstance(step, dict) else {"text": step}
            x = CONTENT_X + i * (node_w + arrow_gap)
            label = _plain(step.get("label"))
            text = _plain(step.get("text") or step.get("body"))
            inner = ((f'<h3 class="do-card-title is-sm" style="margin:0 0 2px;">{_inline(label)}</h3>'
                      if label else "")
                     + (f'<div class="do-body is-sm">{_rich(text)}</div>' if text else ""))
            out.append(_card(_box(x, node_y, node_w, node_h), inner,
                             tone=step.get("tone") or "plain", pad="sm",
                             extra="is-step"))
            if i < count - 1:
                ax = x + node_w + max(2.0, arrow_gap * 0.15)
                aw = arrow_gap - 2 * max(2.0, arrow_gap * 0.15)
                out.append(f'<div class="do-flow-arrow" style="left:{_px(ax)}px;'
                           f'top:{_px(CONTENT_Y + flow_h / 2 - 4)}px;width:{_px(aw)}px;" '
                           f'aria-hidden="true"></div>')
    if not has_pair:
        return "\n".join(out)
    area_y = CONTENT_Y + flow_h + GAP
    area_h = FOOT_Y - area_y
    verdict_h = _clamp(area_h * 0.16, 34.0, 60.0) if verdict else 0.0
    cards_h = max(80.0, area_h - verdict_h - (14.0 if verdict else 0.0))
    vs_w = 64.0
    card_w = (CONTENT_W - vs_w) / 2.0
    out.append(_card_from_dict(CONTENT_X, area_y, card_w, cards_h,
                               groups.get("left"), default_tone="plain", pad="md"))
    right_x = CONTENT_X + card_w + vs_w
    out.append(_card_from_dict(right_x, area_y, card_w, cards_h,
                               groups.get("right"), default_tone="plain", pad="md"))
    marker = 44.0
    mid_x = CONTENT_X + card_w + vs_w / 2.0
    out.append(f'<div class="do-vs" style="left:{_px(mid_x - marker / 2)}px;'
               f'top:{_px(area_y + cards_h / 2 - marker / 2)}px;'
               f'width:{_px(marker)}px;height:{_px(marker)}px;">{_esc(vs)}</div>')
    if verdict:
        out.append(f'<div class="do-verdict" style="top:{_px(area_y + cards_h + 14.0)}px;'
                   f'height:{_px(verdict_h)}px;">{_inline(verdict)}</div>')
    return "\n".join(out)


def _layout_roadmap(page: Any, deck: Any, index: int, total: int) -> str:
    data = page.data if isinstance(page.data, dict) else {}
    aside = data.get("aside") or {}
    steps = [s for s in (data.get("steps") or []) if s is not None][:4]
    height = CARD_H
    aside_w = 360.0
    out = [_card_from_dict(CONTENT_X, CONTENT_Y, aside_w, height, aside,
                           default_tone="primary", pad="md")]
    x = CONTENT_X + aside_w + GAP
    w = CONTENT_R - x
    if not steps:
        return "\n".join(out)
    count = len(steps)
    row_h = (height - GAP * (count - 1)) / count
    for i, step in enumerate(steps):
        out.append(_roadmap_row(x, CONTENT_Y + i * (row_h + GAP), w, row_h, step, i))
    return "\n".join(out)


def _roadmap_row(x: float, y: float, w: float, h: float, step: Any, index: int) -> str:
    """One roadmap row: navy number disc + title/body/meta text inside the card."""
    step = step if isinstance(step, dict) else {"title": str(step)}
    number = _plain(step.get("no")) or str(index + 1)
    card = _card(_box(x, y, w, h), "", tone=step.get("tone") or "plain",
                 accent="teal", accent_side="left", pad="sm")
    disc = (f'<div class="do-step-no" style="left:{_px(x + 12.0)}px;'
            f'top:{_px(y + 14.0)}px;">{_esc(number)}</div>')
    text_x = x + 12.0 + 40.0 + 16.0
    text_w = x + w - text_x
    inner = _inner(title=step.get("title"), title_sm=True, body=step.get("body"),
                   body_sm=True, items=step.get("items"), footer=step.get("meta"))
    text = (f'<div style="position:absolute;left:{_px(text_x)}px;top:{_px(y + 14.0)}px;'
            f'width:{_px(text_w)}px;height:{_px(max(16.0, h - 22.0))}px;">{inner}</div>')
    return card + disc + text


def _chart_card(x: float, y: float, w: float, h: float, chart: Any) -> str:
    chart = chart if isinstance(chart, dict) else {}
    pad = 20.0
    inner_w = max(80.0, w - 2 * pad)
    title = _plain(chart.get("title"))
    unit = _plain(chart.get("unit"))
    note = _plain(chart.get("note"))
    parts: List[str] = []
    header_h = 0.0
    if title:
        parts.append(f'<h3 class="do-card-title" style="margin:0;font-size:16px;">'
                     f'{_inline(title)}</h3>')
        header_h = 24.0
    if unit:
        parts.append(f'<span class="do-chip-en" style="position:absolute;'
                     f'right:{_px(pad)}px;top:{_px(pad + 4)}px;">{_esc(unit)}</span>')
    body_top = pad + header_h + (12.0 if header_h else 0.0)
    reserve = (24.0 if note else 0.0) + 12.0
    avail = max(120.0, h - body_top - reserve)
    chart_h = _clamp(_as_float(chart.get("height"), 320.0), 160.0, avail)
    parts.append(f'<div class="do-chart-wrap" style="left:{_px(pad)}px;top:{_px(body_top)}px;'
                 f'width:{_px(inner_w)}px;height:{_px(chart_h)}px;">'
                 f'{chart_svg(chart, inner_w, chart_h)}</div>')
    if note:
        parts.append(f'<div class="do-card-foot" style="position:absolute;left:{_px(pad)}px;'
                     f'bottom:10px;width:{_px(inner_w)}px;margin:0;">{_inline(note)}</div>')
    return f'<div class="do-card do-tone-plain" style="{_box(x, y, w, h)}padding:{_px(pad)}px;">' \
           + "".join(parts) + "</div>"


def _layout_chart_insight(page: Any, deck: Any, index: int, total: int) -> str:
    data = page.data if isinstance(page.data, dict) else {}
    chart = data.get("chart") or {}
    ratio = _clamp(_as_float(data.get("side_ratio"), 0.60), 0.45, 0.68)
    height = CARD_H
    left_w = (CONTENT_W - GAP) * ratio
    right_x = CONTENT_X + left_w + GAP
    right_w = CONTENT_R - right_x

    out = [_chart_card(CONTENT_X, CONTENT_Y, left_w, height, chart)]

    blocks: List[Dict[str, Any]] = []
    for kpi in (data.get("kpis") or [])[:3]:
        if isinstance(kpi, dict):
            blocks.append({"kind": "kpi", "data": kpi})
        elif kpi is not None:
            blocks.append({"kind": "kpi", "data": {"value": kpi}})
    for card in (data.get("cards") or []):
        if card is not None:
            blocks.append({"kind": "card", "data": card})
    takeaway = data.get("takeaway")
    if isinstance(takeaway, dict) and (takeaway.get("text") or takeaway.get("label")):
        blocks.append({"kind": "takeaway", "data": takeaway})

    if not blocks:
        return "\n".join(out)
    count = len(blocks)
    gap = GAP if count <= 4 else 12.0
    avail = height - gap * (count - 1)
    needs: List[float] = []
    for block in blocks:
        if block["kind"] == "kpi":
            needs.append(133.0)                          # layouts: (CARD_H - 2*GAP) / 3
        elif block["kind"] == "takeaway":
            needs.append(150.0)                          # layouts: navy card is 150 high
        else:
            needs.append(100.0)
    total_need = sum(needs) or 1.0
    scale = min(1.0, avail / total_need)
    heights = [need * scale for need in needs]
    slack = avail - sum(heights)
    if slack > 0:
        heights = [h + slack / count for h in heights]
    heights[-1] = avail - sum(heights[:-1])
    for i, block in enumerate(blocks):
        y = CONTENT_Y + sum(heights[:i]) + i * gap
        block_h = max(40.0, heights[i])
        data_block = block["data"] if isinstance(block["data"], dict) else {"body": block["data"]}
        if block["kind"] == "kpi":
            card_tone, value_tone = _split_tone(data_block.get("tone"))
            if block_h >= 118.0:
                value_class = ""
            elif block_h >= 92.0:
                value_class = "is-sm"
            else:
                value_class = "is-xs"
            note = data_block.get("note") if block_h >= 92.0 else None
            inner = _inner(label=data_block.get("label"), value=data_block.get("value"),
                           unit=data_block.get("unit"), value_class=value_class,
                           value_tone=value_tone or "primary", note=note)
            out.append(_card(_box(right_x, y, right_w, block_h), inner,
                             tone=card_tone or "plain", pad="sm"))
        elif block["kind"] == "takeaway":
            label = _plain(data_block.get("label")) or "结论"
            inner = (f'<p class="do-label">{_esc(label)}</p>'
                     f'<div class="do-body">{_rich(data_block.get("text"))}</div>')
            out.append(_card(_box(right_x, y, right_w, block_h), inner,
                             tone="primary", pad="sm"))
        else:
            out.append(_card_from_dict(right_x, y, right_w, block_h, data_block,
                                       default_tone="tint", title_sm=True, pad="sm",
                                       body_sm=block_h < 110.0))
    return "\n".join(out)


def _resolve_image(path: str, base_dir: Optional[str]) -> str:
    """Locate a figure without pulling in python-pptx.

    Same rule as :func:`deepocean.primitives.resolve_asset`: absolute wins, a
    relative path is tried against the deck's folder first, then the CWD.
    """
    candidate = _plain(path)
    if not candidate:
        return ""
    expanded = os.path.expanduser(candidate)
    options = []
    if os.path.isabs(expanded):
        options.append(expanded)
    if base_dir:
        options.append(os.path.join(base_dir, expanded))
    options.append(os.path.abspath(expanded))
    for option in options:
        if os.path.exists(option):
            return option
    return ""


def _data_uri(path: str, base_dir: Optional[str] = None) -> str:
    """Inline a figure as a data URI so the HTML stays one portable file."""
    import base64
    import mimetypes

    resolved = _resolve_image(path, base_dir)
    if not resolved:
        return ""
    mime = mimetypes.guess_type(resolved)[0] or "image/png"
    try:
        with open(resolved, "rb") as fh:
            payload = base64.b64encode(fh.read()).decode("ascii")
    except OSError:
        return ""
    return f"data:{mime};base64,{payload}"


def _figure_card(x: float, y: float, w: float, h: float, image: Any,
                 base_dir: Optional[str] = None) -> str:
    """Left card of ``image_evidence``: the figure plus its caption and source."""
    image = image if isinstance(image, dict) else {}
    pad = 20.0
    inner_w = max(80.0, w - 2 * pad)
    title = _plain(image.get("title"))
    caption = _plain(image.get("caption"))
    source = _plain(image.get("source"))
    uri = _data_uri(_plain(image.get("path")), base_dir)

    head: List[str] = []
    header_h = 0.0
    if title:
        head.append(f'<h3 class="do-card-title" style="margin:0;font-size:16px;">'
                    f'{_inline(title)}</h3>')
        header_h = 24.0
    foot_h = (24.0 if caption else 0.0) + (18.0 if source else 0.0)
    body_top = pad + header_h + (12.0 if header_h else 0.0)
    avail = max(80.0, h - body_top - foot_h - 12.0)

    if uri:
        frame = (f'<div style="position:absolute;left:{_px(pad)}px;top:{_px(body_top)}px;'
                 f'width:{_px(inner_w)}px;height:{_px(avail)}px;display:flex;'
                 f'align-items:center;justify-content:center;border:1px solid var(--do-line);'
                 f'border-radius:4px;overflow:hidden;background:#fff;">'
                 f'<img src="{uri}" alt="{_esc(caption or title or "figure")}" '
                 f'style="max-width:100%;max-height:100%;object-fit:contain;display:block;">'
                 f'</div>')
    else:
        frame = (f'<div style="position:absolute;left:{_px(pad)}px;top:{_px(body_top)}px;'
                 f'width:{_px(inner_w)}px;height:{_px(avail)}px;border:1px dashed var(--do-line);'
                 f'border-radius:4px;background:var(--do-light);display:flex;'
                 f'align-items:center;justify-content:center;color:var(--do-t3);font-size:12px;">'
                 f'配图缺失 · image not found</div>')
    head.append(frame)
    if caption:
        head.append(f'<div class="do-card-foot" style="position:absolute;left:{_px(pad)}px;'
                    f'bottom:{_px(12.0 + (18.0 if source else 0.0))}px;'
                    f'width:{_px(inner_w)}px;margin:0;">{_inline(caption)}</div>')
    if source:
        head.append(f'<div class="do-card-foot" style="position:absolute;left:{_px(pad)}px;'
                    f'bottom:8px;width:{_px(inner_w)}px;margin:0;color:var(--do-t3);">'
                    f'{_esc(source)}</div>')
    return (f'<div class="do-card do-tone-plain" style="{_box(x, y, w, h)}'
            f'padding:{_px(pad)}px;">' + "".join(head) + "</div>")


def _layout_image_evidence(page: Any, deck: Any, index: int, total: int) -> str:
    data = page.data if isinstance(page.data, dict) else {}
    image = data.get("image") or {}
    ratio = _clamp(_as_float(data.get("side_ratio"), 0.62), 0.50, 0.72)
    left_w = (CONTENT_W - GAP) * ratio
    right_x = CONTENT_X + left_w + GAP
    right_w = CONTENT_R - right_x
    base_dir = os.path.dirname(getattr(deck, "source_path", "") or "") or None

    out = [_figure_card(CONTENT_X, CONTENT_Y, left_w, CARD_H, image, base_dir)]

    blocks: List[Dict[str, Any]] = []
    for card in (data.get("cards") or [])[:3]:
        if isinstance(card, dict):
            blocks.append({"kind": "card", "data": card})
    takeaway = data.get("takeaway")
    if isinstance(takeaway, dict) and (takeaway.get("text") or takeaway.get("label")):
        blocks.append({"kind": "takeaway", "data": takeaway})
    if not blocks:
        return "\n".join(out)

    count = len(blocks)
    gap = GAP
    avail = CARD_H - gap * (count - 1)
    needs = [120.0 if b["kind"] == "takeaway" else 104.0 for b in blocks]
    total_need = sum(needs) or 1.0
    scale = min(1.0, avail / total_need)
    heights = [n * scale for n in needs]
    slack = avail - sum(heights)
    if slack > 0:
        heights = [h + slack / count for h in heights]
    heights[-1] = avail - sum(heights[:-1])
    for i, block in enumerate(blocks):
        y = CONTENT_Y + sum(heights[:i]) + i * gap
        block_h = max(40.0, heights[i])
        data_block = block["data"]
        if block["kind"] == "takeaway":
            label = _plain(data_block.get("label")) or "解读"
            inner = (f'<p class="do-label">{_esc(label)}</p>'
                     f'<div class="do-body">{_rich(data_block.get("text"))}</div>')
            out.append(_card(_box(right_x, y, right_w, block_h), inner,
                             tone="primary", pad="sm"))
        else:
            out.append(_card_from_dict(right_x, y, right_w, block_h, data_block,
                                       default_tone="plain", title_sm=True, pad="sm",
                                       body_sm=block_h < 110.0))
    return "\n".join(out)


def _layout_split_cards(page: Any, deck: Any, index: int, total: int) -> str:
    data = page.data if isinstance(page.data, dict) else {}
    ratio = _clamp(_as_float(data.get("ratio"), 0.56), 0.45, 0.62)
    height = CARD_H
    left_w = (CONTENT_W - GAP) * ratio
    right_x = CONTENT_X + left_w + GAP
    right_w = CONTENT_R - right_x
    right = data.get("right") or {}
    right = right if isinstance(right, dict) else {"body": right}
    left = data.get("left") or {}
    return "\n".join([
        _card_from_dict(CONTENT_X, CONTENT_Y, left_w, height, left,
                        default_tone="accent", accent="teal", accent_side="top",
                        pad="md"),
        _card_from_dict(right_x, CONTENT_Y, right_w, height, right,
                        default_tone="tint", accent="brick", accent_side="top",
                        pad="md"),
    ])


def _layout_concept_flow(page: Any, deck: Any, index: int, total: int) -> str:
    data = page.data if isinstance(page.data, dict) else {}
    left = data.get("left") or {}
    right = data.get("right") or {}
    center = data.get("center") or {}
    if not isinstance(center, dict):
        center = {"label": center}
    take = _plain(data.get("takeaway"))
    take_h = 42.0 if take else 0.0
    card_h = CARD_H - (take_h + 14.0 if take else 0.0)
    left_w = 580.0
    center_x, center_w = 625.0, 30.0
    right_x = 660.0
    right_w = CONTENT_R - right_x

    out = [
        _card_from_dict(CONTENT_X, CONTENT_Y, left_w, card_h, left,
                        default_tone="plain", accent="teal", accent_side="left",
                        pad="md"),
        _card_from_dict(right_x, CONTENT_Y, right_w, card_h, right,
                        default_tone="tint", accent="navy", accent_side="left",
                        pad="md"),
    ]
    mid_y = CONTENT_Y + card_h / 2.0
    out.append(f'<div class="do-center-arrow" style="left:{_px(center_x + 2.0)}px;'
               f'top:{_px(mid_y - 4.0)}px;width:{_px(center_w - 4.0)}px;" '
               f'aria-hidden="true"></div>')
    label = _plain(center.get("label"))
    note = _plain(center.get("note"))
    if label:
        out.append(f'<div class="do-center-label" style="left:{_px(center_x - 90.0)}px;'
                   f'top:{_px(mid_y - 46.0)}px;width:{_px(center_w + 180.0)}px;">'
                   f'{_inline(label)}</div>')
    if note:
        out.append(f'<div class="do-center-note" style="left:{_px(center_x - 90.0)}px;'
                   f'top:{_px(mid_y - 24.0)}px;width:{_px(center_w + 180.0)}px;">'
                   f'{_inline(note)}</div>')
    if take:
        out.append(f'<div class="do-verdict" style="top:{_px(CONTENT_Y + card_h + 14.0)}px;'
                   f'height:{_px(take_h)}px;">{_rich(take)}</div>')
    return "\n".join(out)


def _layout_matrix2x2(page: Any, deck: Any, index: int, total: int) -> str:
    data = page.data if isinstance(page.data, dict) else {}
    aside = data.get("aside") or {}
    if not isinstance(aside, dict):
        aside = {"body": aside}
    quadrants = [q for q in (data.get("quadrants") or []) if q is not None]
    center_label = _plain(data.get("center_label"))
    axes = aside.get("axes") or {}
    if not isinstance(axes, dict):
        axes = {}

    axes_bits = []
    if _plain(axes.get("y")):
        axes_bits.append(_plain(axes.get("y")))
    if _plain(axes.get("x")):
        axes_bits.append(_plain(axes.get("x")))
    aside_body = _inner(title=aside.get("title"), body=aside.get("body"),
                        items=aside.get("items"), footer=aside.get("footer"))
    if axes_bits:
        aside_body += (f'<div class="do-card-foot" style="margin-top:auto;padding-top:8px;'
                       f'border-top:1px solid var(--do-line);">{_esc("  ·  ".join(axes_bits))}</div>')
    out = [_card(_box(CONTENT_X, CONTENT_Y, 340, 430.0), aside_body,
                 tone=aside.get("tone") or "tint", pad="md")]

    area_x, area_w, area_h = 400.0, CONTENT_R - 400.0, 400.0
    q_w = (area_w - GAP) / 2.0
    q_h = (area_h - GAP) / 2.0
    default_tones = ("accent", "danger", "neutral", "tint")
    fill_stroke = {"accent": "teal", "danger": "brick", "alert": "brick",
                   "neutral": "grayblue", "tint": "grayblue", "primary": "navy",
                   "plain": "line"}
    positions = [(0, 0), (1, 0), (0, 1), (1, 1)]     # LT RT LB RB
    for i, quadrant in enumerate(quadrants[:4]):
        col, row = positions[i]
        x = area_x + col * (q_w + GAP)
        y = CONTENT_Y + row * (q_h + GAP)
        quad = quadrant if isinstance(quadrant, dict) else {"title": str(quadrant)}
        tone = str(quad.get("tone") or default_tones[i]).strip().lower()
        stroke = fill_stroke.get(tone, "line")
        parts = []
        no = _plain(quad.get("no"))
        title = _plain(quad.get("title"))
        if no or title:
            no_html = f'<span class="do-quad-no">{_esc(no)}</span>' if no else ""
            parts.append(f'<h3 class="do-quad-title">{no_html}{_inline(title)}</h3>')
        if quad.get("condition"):
            parts.append(f'<div class="do-quad-line">'
                         f'<span class="do-quad-mark">条件 · </span>'
                         f'{_inline(quad.get("condition"))}</div>')
        if quad.get("result"):
            parts.append(f'<div class="do-quad-line is-result">'
                         f'<span class="do-quad-mark">结果 · </span>'
                         f'{_inline(quad.get("result"))}</div>')
        if quad.get("note"):
            parts.append(f'<div class="do-quad-note">{_inline(quad.get("note"))}</div>')
        out.append(_card(_box(x, y, q_w, q_h), "".join(parts), tone=tone, pad="md",
                         border_accent=True, accent=stroke, extra="is-radius-sm"))

    dot = 20.0
    dot_x = area_x + q_w + GAP / 2.0 - dot / 2.0
    dot_y = CONTENT_Y + q_h + GAP / 2.0 - dot / 2.0
    out.append(f'<div class="do-matrix-dot" style="left:{_px(dot_x)}px;top:{_px(dot_y)}px;" '
               f'aria-hidden="true"></div>')
    if center_label:
        out.append(f'<div class="do-matrix-center" style="left:{_px(dot_x + dot + 8)}px;'
                   f'top:{_px(dot_y + dot / 2 - 11)}px;">{_esc(center_label)}</div>')
    if _plain(axes.get("x")):
        out.append(f'<div class="do-axis-x" style="left:{_px(area_x)}px;width:{_px(area_w)}px;'
                   f'top:{_px(CONTENT_Y + area_h + 10.0)}px;text-align:center;">'
                   f'{_inline(axes.get("x"))}</div>')
    if _plain(axes.get("y")):
        out.append(f'<div class="do-axis-y" style="left:{_px(area_x - 22.0)}px;'
                   f'top:{_px(CONTENT_Y + area_h)}px;width:{_px(area_h)}px;">'
                   f'{_inline(axes.get("y"))}</div>')
    return "\n".join(out)


def _col_widths(count: int) -> List[float]:
    if count <= 0:
        return []
    if count == 1:
        return [100.0]
    if count == 2:
        first = 34.0
    elif count == 3:
        first = 28.0
    else:
        first = 22.0
    rest = (100.0 - first) / (count - 1)
    return [first] + [rest] * (count - 1)


def _cell_text(value: Any) -> str:
    if isinstance(value, dict):
        if value.get("text") is not None:
            return _plain(value.get("text"))
        return _plain(value)
    return _plain(value)


def _layout_data_table(page: Any, deck: Any, index: int, total: int) -> str:
    data = page.data if isinstance(page.data, dict) else {}
    columns = [_plain(c) for c in (data.get("columns") or [])]
    raw_rows = data.get("rows") or []
    caption = _plain(data.get("caption"))
    highlight = _as_int(data.get("highlight_col"), -1)
    first_bold = data.get("first_col_bold")
    if first_bold is None:
        first_bold = True

    rows: List[List[str]] = []
    for raw in raw_rows:
        if isinstance(raw, dict):
            cells = raw.get("cells")
            if cells is None:
                cells = [v for v in raw.values()]
        elif isinstance(raw, (list, tuple)):
            cells = list(raw)
        else:
            cells = [raw]
        rows.append([_cell_text(c) for c in cells])

    col_count = max([len(columns)] + [len(r) for r in rows] + [0])
    if col_count == 0:
        return _card(_box(CONTENT_X, CONTENT_Y, CONTENT_W, CARD_H),
                     _inner(title=page.title, body="（本页暂无数据）"), tone="tint", pad="md")
    if len(columns) < col_count:
        columns += [f"列 {i + 1}" for i in range(len(columns), col_count)]
    widths = _col_widths(col_count)

    row_count = max(1, len(rows))
    head_h = 42.0
    caption_h = 22.0 if caption else 0.0
    row_h = min(52.0, max(44.0, 430.0 / row_count))     # guide: rows 44-52 px
    table_h = head_h + row_count * row_h + caption_h + 8.0
    top = CONTENT_Y + max(0.0, (CARD_H - table_h) / 2.0)

    density = "is-airy" if row_count <= 5 else ("is-dense" if row_count > 8 else "")

    head = "".join(f'<th scope="col">{_esc(c)}</th>' for c in columns[:col_count])
    colgroup = "".join(f'<col style="width:{_px(w)}%;"/>' for w in widths)
    body_rows = []
    for row in rows:
        cells = row + [""] * (col_count - len(row))
        tds = []
        for i in range(col_count):
            text = cells[i]
            classes = []
            if i == 0 and first_bold:
                classes.append("is-first")
            if _looks_numeric(text):
                classes.append("is-num")
            if i == highlight:
                negative = str(text).strip()[:1] in ("-", "−")
                classes.append("is-hl-neg" if negative else "is-hl")
            cls = f' class="{" ".join(classes)}"' if classes else ""
            tds.append(f"<td{cls}>{_inline(text)}</td>")
        body_rows.append(f'<tr style="height:{_px(row_h)}px;">' + "".join(tds) + "</tr>")

    caption_html = f'<div class="do-table-caption">{_inline(caption)}</div>' if caption else ""
    return (f'<div class="do-table-wrap" style="left:{_px(CONTENT_X)}px;top:{_px(top)}px;'
            f'width:{_px(CONTENT_W)}px;height:{_px(table_h)}px;">'
            f'<table class="do-table {density}"><colgroup>{colgroup}</colgroup>'
            f'<thead><tr style="height:{_px(head_h)}px;">{head}</tr></thead>'
            f'<tbody>{"".join(body_rows)}</tbody></table>'
            f'{caption_html}'
            f'</div>')


def _layout_key_findings(page: Any, deck: Any, index: int, total: int) -> str:
    data = page.data if isinstance(page.data, dict) else {}
    banner = data.get("banner") or {}
    banner = banner if isinstance(banner, dict) else {"heading": banner}
    cards = [c for c in (data.get("cards") or []) if c is not None][:3]
    ratio = _clamp(_as_float(data.get("cards_ratio"), 0.46), 0.40, 0.56)

    out: List[str] = []
    has_banner = bool(banner.get("heading") or banner.get("figures"))
    banner_h = 110.0 if has_banner else 0.0
    if has_banner:
        head = _plain(banner.get("heading"))
        kicker = _plain(banner.get("label"))
        head_html = ""
        if head or kicker:
            inner = (f'<span class="do-banner-kicker">{_esc(kicker)}</span>' if kicker else "") + _esc(head)
            head_html = f'<p class="do-banner-head">{inner}</p>'
        figs = []
        for figure in (banner.get("figures") or []):
            figure = figure if isinstance(figure, dict) else {"value": figure}
            _, value_tone = _split_tone(figure.get("tone"))
            value_cls = _value_class(value_tone) or "do-u-teal"
            unit = f'<span class="do-fig-unit">{_esc(figure.get("unit"))}</span>' if figure.get("unit") else ""
            figs.append(f'<div class="do-fig"><p class="do-fig-value {value_cls}">'
                        f'{_inline(figure.get("value"))}{unit}</p>'
                        f'<p class="do-fig-label">{_inline(figure.get("label"))}</p></div>')
        figs_html = f'<div class="do-banner-figs">{"".join(figs)}</div>' if figs else ""
        if not figs and head_html:
            head_html = head_html.replace('class="do-banner-head"',
                                          'class="do-banner-head" style="flex:1 1 auto;"')
        out.append(f'<div class="do-banner" style="top:{_px(CONTENT_Y)}px;'
                   f'width:{_px(CONTENT_W)}px;height:{_px(banner_h)}px;">'
                   f'{head_html}{figs_html}</div>')
    cards_y = CONTENT_Y + (banner_h + GAP if has_banner else 0.0)
    cards_h = FOOT_Y - cards_y
    if not cards:
        return "\n".join(out)
    count = len(cards)
    first_w = (CONTENT_W - GAP) * ratio if count > 1 else CONTENT_W
    out.append(_card_from_dict(CONTENT_X, cards_y, first_w, cards_h, cards[0],
                               default_tone="plain", pad="md"))
    if count == 1:
        return "\n".join(out)
    rx = CONTENT_X + first_w + GAP
    rw = CONTENT_R - rx
    rest = count - 1
    each = (rw - GAP * (rest - 1)) / rest
    for i, card in enumerate(cards[1:]):
        tone = ""
        if isinstance(card, dict):
            tone, _ = _split_tone(card.get("tone"))
        default_tone = "tint" if i == 0 else "accent"
        out.append(_card_from_dict(rx + i * (each + GAP), cards_y, each, cards_h, card,
                                   default_tone=default_tone, title_sm=True, pad="md"))
    return "\n".join(out)


def _layout_closing(page: Any, deck: Any, index: int, total: int) -> str:
    """Closing: 100px bar, quote 140/190, panels y=350 h=270, thanks strip 648."""
    data = page.data if isinstance(page.data, dict) else {}
    quote = data.get("quote") or {}
    quote = quote if isinstance(quote, dict) else {"text": quote}
    panels = [p for p in (data.get("panels") or []) if p is not None][:3]
    thanks = _plain(data.get("thanks"))

    out = [_topbar(deck, page, tall=True, show_series=False)]
    title = page.title or getattr(deck.meta, "kicker", "") or "总结与展望"
    out.append(f'<h2 class="do-close-title">{_inline(title)}</h2>')
    series = data.get("series") or deck.meta.journal
    if series:
        out.append(f'<div class="do-close-series">{_esc(series)}</div>')
    out.append('<div class="do-close-rule"></div>')

    text = _plain(quote.get("text"))
    source = _plain(quote.get("source"))
    quote_inner = ""
    if text:
        size = 22.0
        while size > 16.0 and _wrap_count(text, size, 1120.0, True) > 2:
            size -= 0.5
        quote_inner += (f'<p class="do-quote-text" style="font-size:{_px(size)}px;">'
                        f'{_inline(text)}</p>')
    if source:
        quote_inner += f'<p class="do-quote-src">— {_inline(_truncate(source, 12, 1100.0))}</p>'
    out.append(f'<div class="do-quote">{quote_inner}</div>')

    panels_y, panels_h = 350.0, 270.0
    if panels:
        count = len(panels)
        first_w = CONTENT_W if count == 1 else 560.0
        rest_w = 0.0 if count == 1 else (CONTENT_W - first_w - GAP * (count - 1)) / (count - 1)
        x = CONTENT_X
        for i, panel in enumerate(panels):
            w = first_w if i == 0 else rest_w
            tone = ""
            if isinstance(panel, dict):
                tone, _ = _split_tone(panel.get("tone"))
            out.append(_card_from_dict(x, panels_y, w, panels_h, panel,
                                       default_tone="plain" if i == 0 else "primary",
                                       pad="md"))
            x += w + GAP

    if thanks:
        out.append('<div class="do-thanks"><span class="do-thanks-label">致谢</span>'
                   f'<span>{_inline(thanks)}</span></div>')
    out.append('<div class="do-close-band"></div>')
    return "\n".join(out)


def _layout_fallback(page: Any, deck: Any, index: int, total: int) -> str:
    """Unknown layout: dump the declared data instead of raising."""
    data = page.data if isinstance(page.data, dict) else {}
    rows = []
    for key, value in data.items():
        text = _plain(value)
        if not text:
            continue
        rows.append(f'<li><b class="do-lead">{_esc(key)}</b> {_esc(text)}</li>')
    items = f'<ul class="do-items is-plain">{"".join(rows)}</ul>' if rows else ""
    inner = _inner(title=page.title, body=f"未知版式：{_plain(page.layout)}", footer=items)
    return _card(_box(CONTENT_X, CONTENT_Y, CONTENT_W, CARD_H), inner,
                 tone="tint", accent="grayblue", accent_side="left", pad="lg")


_LAYOUT_RENDERERS: Dict[str, Callable[[Any, Any, int, int], str]] = {
    "cover": _layout_cover,
    "two_column": _layout_two_column,
    "big_number": _layout_big_number,
    "experiment_design": _layout_experiment_design,
    "roadmap": _layout_roadmap,
    "chart_insight": _layout_chart_insight,
    "split_cards": _layout_split_cards,
    "concept_flow": _layout_concept_flow,
    "matrix2x2": _layout_matrix2x2,
    "image_evidence": _layout_image_evidence,
    "data_table": _layout_data_table,
    "key_findings": _layout_key_findings,
    "closing": _layout_closing,
}


# --------------------------------------------------------------------------- #
# Pages and documents
# --------------------------------------------------------------------------- #


def _layout_key(name: Any) -> str:
    try:
        return schema.resolve(_plain(name))
    except KeyError:
        return _plain(name).strip().lower().replace(" ", "_")


def _needs_chrome(layout: str) -> bool:
    try:
        return schema.needs_chrome(layout)
    except KeyError:
        return True


def render_page(page: Any, deck: Any, index: int, total: int) -> str:
    """Render one ``<section class="do-page">`` (1280 x 720 px canvas)."""
    layout = _layout_key(getattr(page, "layout", ""))
    meta = schema.LAYOUTS.get(layout) or {}
    layout_zh = meta.get("zh", layout)
    chrome = meta.get("chrome", True) if meta else _needs_chrome(layout)

    label_title = getattr(page, "title", "") or ""
    if not label_title and layout in ("cover", "closing"):
        label_title = getattr(getattr(deck, "meta", None), "title", "") or ""
    aria = f"第 {index} 页 {layout_zh}"
    if label_title:
        aria += f"：{label_title}"

    parts: List[str] = []
    if chrome:
        parts.append(_topbar(deck, page))
        parts.append(_title_block(page))
    renderer = _LAYOUT_RENDERERS.get(layout, _layout_fallback)
    parts.append(renderer(page, deck, index, total))
    if chrome or layout in _EXTRA_FOOTER_LAYOUTS:
        parts.append(_footer(deck, index, total))
    return (f'<section class="do-page" data-layout="{_esc(layout)}" data-page="{index}" '
            f'aria-label="{_esc(aria)}">\n' + "\n".join(parts) + "\n</section>")


def _toolbar(deck: Any) -> str:
    total = len(getattr(deck, "pages", []) or [])
    return ('<div class="do-toolbar" role="note">'
            '<span class="do-toolbar-brand">DEEP OCEAN</span>'
            f'<span class="do-toolbar-meta">共 {total} 页 · 1280 × 720 px · 16:9</span>'
            '<span class="do-toolbar-hint">按 Ctrl / Cmd + P 打印或导出 PDF（每页一张画布）</span>'
            '</div>')


def render_fragment(deck: Any) -> str:
    """Body markup only — every page wrapped in ``<div class="do-deck">``."""
    pages = list(getattr(deck, "pages", []) or [])
    if not pages:
        return ('<div class="do-deck"><p class="do-empty">'
                '这份 deck 还没有页面 · this deck has no pages</p></div>')
    total = len(pages)
    chunks = [render_page(page, deck, i, total) for i, page in enumerate(pages, 1)]
    return '<div class="do-deck">\n' + "\n".join(chunks) + "\n</div>"


def _document(deck: Any, title_text: str, body: str) -> str:
    lines = [
        "<!DOCTYPE html>",
        '<html lang="zh-CN">',
        "<head>",
        '<meta charset="UTF-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1.0">',
        f'<meta name="generator" content="{tokens.NAME} {tokens.VERSION} · deepocean.html">',
        f"<title>{_esc(title_text)}</title>",
        "<style>",
        css().rstrip("\n"),
        "</style>",
        "</head>",
        '<body class="do-body">',
        _toolbar(deck),
        body,
        "</body>",
        "</html>",
        "",
    ]
    return "\n".join(lines)


def render(deck: Any, *, standalone: bool = True, title: Optional[str] = None) -> str:
    """Render a whole deck to HTML.

    ``standalone=True`` returns one self-contained document with the stylesheet
    inlined; ``standalone=False`` returns the bare body markup (the same as
    :func:`render_fragment`) for embedding into an existing page.
    """
    body = render_fragment(deck)
    if not standalone:
        return body
    meta = getattr(deck, "meta", None)
    doc_title = title or getattr(meta, "title", "") or f"{tokens.NAME} deck"
    return _document(deck, doc_title, body)


def write(deck: Any, path: str, **kw: Any) -> str:
    """Write the rendered deck to ``path`` (UTF-8, LF) and return the abs path."""
    text = render(deck, **kw)
    target = os.path.abspath(os.fspath(path))
    parent = os.path.dirname(target)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(target, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
    return target


# --------------------------------------------------------------------------- #
# Stylesheet
# --------------------------------------------------------------------------- #


def _template_path(name: str) -> str:
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates", name)


def _read_template(name: str) -> str:
    """Read a bundled template through importlib.resources (fs fallback)."""
    try:
        from importlib.resources import files as _files      # Python >= 3.9
    except ImportError:                                      # pragma: no cover
        _files = None
    if _files is not None:
        package = __package__ or "deepocean"
        try:
            return (_files(package) / "templates" / name).read_text(encoding="utf-8")
        except (FileNotFoundError, ModuleNotFoundError, NotADirectoryError, OSError):
            pass
    path = _template_path(name)
    with open(path, "r", encoding="utf-8") as handle:
        return handle.read()


def _font_name(name: str) -> str:
    text = str(name).strip()
    if text.lower() in _GENERIC_FONTS or " " not in text:
        return text
    return '"%s"' % text


def _font_vars() -> str:
    """``tokens.FONTS`` as CSS custom properties (system fallbacks included)."""
    lines = [":root{"]
    for key in ("cjk", "latin", "serif", "mono"):
        stack = tokens.FONTS.get(key) or []
        if not stack:
            continue
        value = ", ".join(_font_name(item) for item in stack)
        lines.append(f"  --do-font-{key}:{value};")
    lines.append("}")
    return "\n".join(lines)


def css() -> str:
    """The renderer stylesheet, with tokens + font stacks injected."""
    raw = _read_template("deck.css")
    if _TEMPLATE_MARKER in raw:
        raw = raw.replace(_TEMPLATE_MARKER, tokens.css_variables())
    if _FONT_MARKER in raw:
        raw = raw.replace(_FONT_MARKER, _font_vars())
    return raw
