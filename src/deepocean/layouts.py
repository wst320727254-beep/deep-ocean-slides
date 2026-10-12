# -*- coding: utf-8 -*-
"""The twelve Deep Ocean page layouts, drawn as real PowerPoint geometry.

Every renderer consumes exactly the fields declared for its layout in
:mod:`deepocean.schema` and composes the components in
:mod:`deepocean.components`; nothing here touches python-pptx directly except
through the frozen primitives.

Contract
--------
``RENDERERS`` maps a :data:`deepocean.schema.LAYOUTS` key to a
``render_<layout>(slide, page, ctx)`` callable, and :func:`build_page` is the
only entry point a builder should call::

    from deepocean import layouts
    layouts.build_page(slide, page, ctx)   # chrome first, then the layout

Geometry is quoted in design px on the 1280 x 720 canvas with a 40px safe
margin: the content band is ``y 200 -> 640`` (cards 430-440 high, 20px gutters),
the shared chrome lives in bands A/B/D, and cover / closing pages may break the
bands because they draw their own chrome.

Required fields raise :class:`deepocean.spec.SpecError` through ``page.need``;
optional fields are tolerated when absent.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Sequence

from . import schema, tokens
from .charts import add_chart, chart_height
from .components import (bullets as _bullets, card, card_head, compare_pair,
                         estimate_height, master, matrix_grid, process_steps,
                         stat_banner, style_of, table as _table, takeaway)
from .components import footnote as _footnote
from .components import kpi as _kpi
from .components import _para, _render_paras, _wrap_count
from .primitives import add_arrow, hairline, oval, rect, truncate

__all__ = ["RENDERERS", "build_page", "render"]

Shape = Any

# --------------------------------------------------------------------------- #
# Geometry
# --------------------------------------------------------------------------- #

MARGIN = float(tokens.SAFE_MARGIN_PX)          # 40
CANVAS_W = float(tokens.CANVAS["width_px"])    # 1280
CANVAS_H = float(tokens.CANVAS["height_px"])   # 720
CONTENT_X = MARGIN                             # 40
CONTENT_W = float(tokens.CONTENT_WIDTH_PX)     # 1200
CONTENT_R = CONTENT_X + CONTENT_W              # 1240
BAND_Y = float(tokens.BANDS["content"]["y"])   # 200
CARD_H = 440.0
FOOT_Y = 640.0
GAP = float(tokens.CARD_GAP_PX)                # 20


# --------------------------------------------------------------------------- #
# Local helpers
# --------------------------------------------------------------------------- #


def _num(value: Any, fallback: float = 0.0) -> float:
    """Coerce a spec value to a float, tolerating ``None`` / ``""``."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(fallback)


def _clamp(value: Any, lo: float, hi: float, fallback: float) -> float:
    """Clamp a ratio from the deck spec into its documented range."""
    v = _num(value, fallback)
    if v <= 0:
        v = fallback
    return max(lo, min(hi, v))


def _meta(ctx: Any) -> Any:
    """The :class:`deepocean.spec.DeckMeta` behind a render context."""
    return getattr(getattr(ctx, "deck", None), "meta", None)


def _text(slide: Shape, x: float, y: float, w: float, h: float, value: Any, *,
          token: str = "card_body", size: Optional[float] = None,
          color: Optional[str] = None, bold: Optional[bool] = None,
          align: Optional[str] = None, anchor: str = "top",
          line_spacing: Optional[float] = None) -> Dict[str, Any]:
    """Draw one block of text and report the box it used.

    Args:
        slide: Slide to draw on.
        x, y, w, h: Box in design px.
        value: Text (``None`` / ``""`` draws nothing).
        token: Type token key driving the size / weight / colour.
        size: Size override in px.
        color: Palette key override.
        bold: Weight override.
        align: Paragraph alignment (``left`` / ``center`` / ``right``).
        anchor: Vertical anchor (``top`` / ``middle`` / ``bottom``).
        line_spacing: Optional line-height multiplier.

    Returns:
        A box dict with the measured height actually needed.
    """
    body = "" if value is None else str(value)
    if not body:
        return {"x": x, "y": y, "w": w, "h": 0.0, "text": ""}
    st = style_of(token, color=color, size=size, bold=bold)
    para = _para(body, st, align=align, line_spacing=line_spacing or st.get("line_spacing") or 1.4)
    needed = estimate_height([para], w)
    _render_paras(slide, x, y, w, [para], anchor=anchor)
    return {"x": x, "y": y, "w": w, "h": needed, "text": body}


def _page_number_text(ctx: Any) -> str:
    """``"07 / 12"`` style page tag used by the cover-internal decorations."""
    return "{:02d} / {:02d}".format(int(getattr(ctx, "index", 1) or 1),
                                    int(getattr(ctx, "total", 1) or 1))


def _chip_text(value: Any) -> str:
    """Normalise an optional chip label from the spec."""
    return "" if value is None else str(value)


def _list(value: Any) -> List[Any]:
    """Coerce a spec field into a list (``None`` -> ``[]``)."""
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return list(value)
    return [value]


def _dict(value: Any) -> Dict[str, Any]:
    """Coerce a spec field into a dict (``None`` -> ``{}``)."""
    return dict(value) if isinstance(value, dict) else {}


# --------------------------------------------------------------------------- #
# 01 - cover
# --------------------------------------------------------------------------- #


def render_cover(slide: Shape, page: Any, ctx: Any) -> None:
    """Cover page: headline, English sub-headline, author block, info strip.

    Band-free by design (``chrome: False``): it draws its own navy top bar,
    the teal left rule, a colour band at the very bottom, and no footer.
    """
    meta = _meta(ctx)
    title = str(page.title or (getattr(meta, "title", "") or "") or "Untitled deck")
    english = str(page.title_en or page.get("english_title", "")
                  or getattr(meta, "subtitle", "") or "")
    authors = str(page.get("authors", "") or ", ".join(getattr(meta, "authors", []) or []))
    affiliation = str(page.get("affiliation", "") or getattr(meta, "affiliation", "") or "")
    series = str(page.get("series", "") or getattr(meta, "journal", "") or "")
    note = str(page.get("note", "") or getattr(meta, "source_note", "")
               or getattr(meta, "subtitle", "") or "")
    band_text = str(page.get("band", "") or "")
    kicker = str(page.kicker or page.get("kicker", "") or getattr(meta, "kicker", "") or "")

    # Top bar + left rule.
    rect(slide, 0, 0, CANVAS_W, 60, fill="navy")
    rect(slide, 32, 26, 8, 8, fill="teal")
    rect(slide, 0, 120, 6, 480, fill="teal")
    if series:
        _text(slide, 900, 22, 340, 20, truncate(series, 13, 340, False),
              token="footer", size=13, color="white", align="right")

    x = 72.0
    w = 1100.0
    y = 140.0
    if kicker:
        _text(slide, x, y, w, 20, truncate(kicker, 14, w, True).upper(),
              token="kicker", size=14, color="teal", bold=True, line_spacing=1.1)
        y += 26.0
    size = 44.0
    while size > 30.0 and _wrap_count(title, size, w, True) > 2:
        size -= 2.0
    used = _text(slide, x, y, w, 120, title, token="cover_title", size=size,
                 color="navy", bold=True, line_spacing=1.22)
    y += used["h"] + 12.0
    if english:
        used = _text(slide, x, y, w, 70, english, token="cover_subtitle", size=26,
                     color="t1", line_spacing=1.3)
        y += used["h"] + 10.0

    rect(slide, x, 410, 160, 2, fill="teal")

    # The guide pins the author block at 440; a long headline may push into that
    # space, so clamp the block below the divider instead of overlapping it.
    info_y = max(440.0, y + 14.0)
    if authors:
        _text(slide, x, info_y, w, 24, authors, token="cover_meta", size=15,
              color="grayblue", line_spacing=1.3)
    if affiliation:
        _text(slide, x, info_y + 26.0, w, 24, affiliation, token="cover_meta", size=14,
              color="t3", line_spacing=1.3)

    # Bottom info strip + colour band.
    strip_y = 568.0
    rect(slide, 0, strip_y, CANVAS_W, 144, fill="light")
    rect(slide, 0, strip_y, 8, 144, fill="navy")
    if note:
        _text(slide, x, strip_y + 30.0, w, 30, note, token="card_body", size=14,
              color="t2", line_spacing=1.4)
    _text(slide, x, strip_y + 68.0, w, 44, _page_number_text(ctx),
          token="caption", size=11.5, color="t3", line_spacing=1.2)
    if band_text:
        _text(slide, x, strip_y + 92.0, w, 24, band_text, token="caption", size=11.5,
              color="t3", line_spacing=1.2)
    rect(slide, 0, 712, CANVAS_W, 8, fill="navy")


# --------------------------------------------------------------------------- #
# 02 - two_column
# --------------------------------------------------------------------------- #


def _right_column(slide: Shape, x: float, w: float, cards: Sequence[Any], *,
                  y: float = BAND_Y, h: float = CARD_H, bottom_tone: str = "primary") -> List[Dict[str, Any]]:
    """Stack 1-4 cards down a column, the last one carrying the conclusion.

    The final card is tone ``primary`` (navy) when the spec does not ask for a
    specific tone, which gives the column its dark anchor.
    """
    items = [c for c in cards if isinstance(c, dict)]
    if not items:
        return []
    n = len(items)
    ch = (h - GAP * (n - 1)) / n
    out: List[Dict[str, Any]] = []
    for i, item in enumerate(items):
        cy = y + i * (ch + GAP)
        tone = str(item.get("tone") or ("plain" if i < n - 1 else bottom_tone))
        box = card(slide, x, cy, w, ch, tone=tone, pad="sm")
        card_head(slide, box, chip=_chip_text(item.get("chip")),
                  title=str(item.get("title", "") or ""),
                  body=str(item.get("body", "") or ""),
                  items=_list(item.get("items")),
                  footer=str(item.get("footer", "") or ""),
                  title_size=16.0, body_size=13.0, item_size=13.0)
        out.append(box)
    return out


def render_two_column(slide: Shape, page: Any, ctx: Any) -> None:
    """Asymmetric two-column: one wide argument card plus a stacked side column."""
    left = _dict(page.need("left"))
    right = [c for c in _list(page.need("right")) if isinstance(c, dict)]
    ratio = _clamp(page.get("ratio", 0.60), 0.5, 0.7, 0.60)

    left_w = (CONTENT_W - GAP) * ratio
    right_x = CONTENT_X + left_w + GAP
    right_w = CONTENT_W - left_w - GAP

    box = card(slide, CONTENT_X, BAND_Y, left_w, CARD_H, tone="tint", accent="teal",
               accent_side="left", accent_w=6.0, pad="md")
    card_head(slide, box, chip=_chip_text(left.get("chip")),
              chip_en=str(left.get("chip_en", "") or ""),
              title=str(left.get("title", "") or ""),
              body=str(left.get("body", "") or ""),
              items=_list(left.get("items")),
              footer=str(left.get("footer", "") or ""),
              title_size=18.0, body_size=14.0, item_size=14.0)

    _right_column(slide, right_x, right_w, right)


# --------------------------------------------------------------------------- #
# 03 - big_number
# --------------------------------------------------------------------------- #


def _anchor_card(slide: Shape, x: float, y: float, w: float, h: float, item: Dict[str, Any], *,
                 anchor: float, label: str = "") -> Dict[str, Any]:
    """A card whose visual anchor is a very large number.

    Args:
        slide: Slide to draw on.
        x, y, w, h: Card box in px.
        item: ``{number, unit, title, body, tone}`` from the layout spec.
        anchor: Number size in px (44 / 48 / 72 depending on the slot).
        label: Small label drawn above the number.

    Returns:
        The card box dict.
    """
    tone = str(item.get("tone") or "plain")
    box = card(slide, x, y, w, h, tone=tone, pad="md")
    ink = "white" if box.get("fill") == "navy" else "t1"
    color_key = {"up": "teal", "positive": "teal", "down": "brick",
                 "negative": "brick"}.get(tone.lower(), "navy")
    if box.get("fill") == "navy":
        color_key = "teal"
    title = str(item.get("title", "") or "")
    body = str(item.get("body", "") or "")
    cur = float(box["cy"])
    # The label above the number and the title under it are the same words when
    # the item has no body paragraph, so print it once.
    if label and body:
        used = _text(slide, box["cx"], cur, float(box["cw"]), 18,
                     truncate(label, 12, float(box["cw"]), False),
                     token="kpi_label", size=12, color="white" if ink == "white" else "grayblue",
                     line_spacing=1.15)
        cur += used["h"] + 4.0
    num = "" if item.get("number") is None else str(item.get("number"))
    unit = "" if item.get("unit") is None else str(item.get("unit"))
    if num:
        runs = [{"text": num, "style": style_of("kpi_value", size=anchor, color=color_key)}]
        if unit:
            unit_size = max(11.0, anchor * max(0.45, min(0.6, 11.0 / max(1.0, anchor))))
            unit_color = color_key if color_key == "white" else "grayblue"
            runs.append({"text": " " + unit,
                         "style": style_of("kpi_value", size=unit_size, color=unit_color)})
        para = {"runs": runs, "align": None, "space_before": 0.0, "space_after": 4.0,
                "line_spacing": 1.02}
        used_h = estimate_height([para], float(box["cw"]))
        _render_paras(slide, box["cx"], cur, float(box["cw"]), [para])
        cur += used_h + 6.0
    rest = float(box["cy"]) + float(box["ch"]) - cur
    if title and rest > 30.0:
        size = 18.0 if anchor <= 48 else 16.0
        used = _text(slide, box["cx"], cur, float(box["cw"]), rest,
                     truncate(title, size, float(box["cw"]), True),
                     token="card_title", size=size, color=ink, bold=True,
                     line_spacing=1.25)
        cur += used["h"] + 4.0
    if body:
        room = float(box["cy"]) + float(box["ch"]) - cur
        if room > 20.0:
            size = 14.0
            while size > 13.0 and estimate_height(
                    [_para(body, style_of("card_body", size=size, color="white" if ink == "white" else "t2"),
                          line_spacing=1.45)], float(box["cw"])) > room:
                size -= 0.5
            _text(slide, box["cx"], cur, float(box["cw"]), room, body,
                  token="card_body", size=size,
                  color="white" if ink == "white" else "t2", line_spacing=1.45)
    return box


def render_big_number(slide: Shape, page: Any, ctx: Any) -> None:
    """Hero number page: one 72px anchor plus two 48px satellites, or a grid."""
    items = [i for i in _list(page.need("items")) if isinstance(i, dict)][:4]
    if len(items) < 2:
        raise ValueError("big_number needs 2-4 items")
    # The headline number doubles as the label on a single-anchor hero card; the
    # title under it carries the wording, so grid cards pass no label.
    mode = str(page.get("mode", "hero") or "hero").strip().lower()
    if mode == "grid":
        n = len(items)
        if n >= 4:
            # 2x2 so four anchors stay big instead of shrinking into a thin row.
            cw = (CONTENT_W - GAP) / 2.0
            ch = (CARD_H - GAP) / 2.0
            for i, item in enumerate(items[:4]):
                col, row = i % 2, i // 2
                _anchor_card(slide, CONTENT_X + col * (cw + GAP), BAND_Y + row * (ch + GAP),
                             cw, ch, item, anchor=44.0)
            return
        # 2-3 items: one row, the first card leading (never three equal columns).
        weights = [1.25] + [1.0] * (n - 1)
        total = sum(weights)
        cw_list = [w / total * (CONTENT_W - GAP * (n - 1)) for w in weights]
        cx = CONTENT_X
        for item, cw in zip(items, cw_list):
            _anchor_card(slide, cx, BAND_Y, cw, CARD_H, item, anchor=32.0)
            cx += cw + GAP
        return

    left_w = 580.0
    right_x = CONTENT_X + left_w + GAP
    right_w = CONTENT_W - left_w - GAP
    _anchor_card(slide, CONTENT_X, BAND_Y, left_w, CARD_H, items[0], anchor=72.0,
                 label=str(items[0].get("title", "") or ""))
    _anchor_card(slide, right_x, BAND_Y, right_w, 200.0, items[1], anchor=48.0)
    if len(items) > 2:
        _anchor_card(slide, right_x, BAND_Y + 200.0 + GAP, right_w, 210.0, items[2], anchor=48.0)


# --------------------------------------------------------------------------- #
# 04 - experiment_design
# --------------------------------------------------------------------------- #


def render_experiment_design(slide: Shape, page: Any, ctx: Any) -> None:
    """Experiment design: a 2-3 node flow strip above a treatment/control pair."""
    steps = [s for s in _list(page.need("steps")) if s]
    groups = _dict(page.need("groups"))
    vs = str(page.get("vs", "VS") or "VS")
    verdict = str(page.get("verdict", "") or "")

    flow_h = 124.0 if (groups.get("left") or groups.get("right") or verdict) else CARD_H
    process_steps(slide, CONTENT_X, BAND_Y, CONTENT_W, flow_h, steps,
                  node_h=60.0, gap=24.0, tone="plain", size=12.0)

    if flow_h >= CARD_H:
        return
    area_y = BAND_Y + flow_h + GAP
    area_h = FOOT_Y - area_y
    compare_pair(slide, CONTENT_X, area_y, CONTENT_W, area_h,
                 _dict(groups.get("left")), _dict(groups.get("right")),
                 vs=vs, verdict=verdict)


# --------------------------------------------------------------------------- #
# 05 - roadmap
# --------------------------------------------------------------------------- #


def render_roadmap(slide: Shape, page: Any, ctx: Any) -> None:
    """Roadmap: a navy aside panel on the left, 2-4 numbered steps on the right."""
    aside = _dict(page.need("aside"))
    steps = [s for s in _list(page.need("steps")) if s][:4]

    aside_w = 360.0
    box = card(slide, CONTENT_X, BAND_Y, aside_w, CARD_H, tone="primary", pad="md")
    card_head(slide, box, chip=_chip_text(aside.get("chip")),
              title=str(aside.get("title", "") or ""),
              body=str(aside.get("body", "") or ""),
              items=_list(aside.get("items")),
              footer=str(aside.get("footer", "") or ""),
              title_size=18.0, body_size=13.5, item_size=13.0)

    x = CONTENT_X + aside_w + GAP
    w = CONTENT_R - x
    n = max(1, len(steps))
    # A roadmap reads as a list, not as four poster panels: keep each step card
    # compact and let the extra room fall after the last step.
    ch = min((CARD_H - GAP * (n - 1)) / n, 103.0)
    for i, step in enumerate(steps):
        data = _dict(step)
        cy = BAND_Y + i * (ch + GAP)
        step_box = card(slide, x, cy, w, ch, tone="plain", pad="sm",
                        accent="teal", accent_side="left", accent_w=5.0)
        no = str(data.get("no", "") or (i + 1))
        ring = min(40.0, ch - 16.0)
        oval(slide, x + 12.0, cy + (ch - ring) / 2.0, ring, ring, fill="navy")
        _text(slide, x + 12.0, cy + (ch - ring) / 2.0, ring, ring,
              truncate(no, 17, ring - 8.0, True),
              token="card_title", size=17, color="white", align="center",
              anchor="middle", line_spacing=1.05)
        tx = x + 12.0 + ring + 16.0
        tw = float(step_box["cx"]) + float(step_box["cw"]) - tx
        title = str(data.get("title", "") or "")
        body = str(data.get("body", "") or "")
        meta_text = str(data.get("meta", "") or "")
        cur = cy + 12.0
        if title:
            used = _text(slide, tx, cur, tw, 30, truncate(title, 16, tw, True),
                         token="card_title_sm", size=16, color="navy", bold=True,
                         line_spacing=1.2)
            cur += used["h"] + 4.0
        if body:
            room = float(step_box["cy"]) + float(step_box["ch"]) - cur - (18.0 if meta_text else 4.0)
            if room > 16.0:
                size = 13.5
                while size > 13.0 and estimate_height(
                        [_para(body, style_of("card_body", size=size, color="t2"),
                               line_spacing=1.4)], tw) > room:
                    size -= 0.5
                _text(slide, tx, cur, tw, max(16.0, room), body,
                      token="card_body", size=size, color="t2", line_spacing=1.4)
        if meta_text:
            _text(slide, tx, float(step_box["cy"]) + float(step_box["ch"]) - 20.0, tw, 16,
                  truncate(meta_text, 11.5, tw, False), token="caption", size=11.5,
                  color="t3", line_spacing=1.1)


# --------------------------------------------------------------------------- #
# 06 - chart_insight
# --------------------------------------------------------------------------- #


def _chart_number_format(unit: str) -> str:
    """A plain number format (negatives with a minus sign, never parentheses)."""
    unit = str(unit or "").strip()
    if unit == "%":
        return '0.0"%"'
    if unit:
        return f'0.0"{unit}"'
    return "0.##"


def render_chart_insight(slide: Shape, page: Any, ctx: Any) -> None:
    """Chart on the left (real pptx chart) with KPI cards and a conclusion right."""
    chart_spec = _dict(page.need("chart"))
    ratio = _clamp(page.get("side_ratio", 0.60), 0.45, 0.68, 0.60)
    kpis = [k for k in _list(page.get("kpis")) if isinstance(k, dict)][:3]
    cards = [c for c in _list(page.get("cards")) if isinstance(c, dict)]
    take = _dict(page.get("takeaway"))

    left_w = (CONTENT_W - GAP) * ratio
    right_x = CONTENT_X + left_w + GAP
    right_w = CONTENT_W - left_w - GAP

    # -- left: chart card ------------------------------------------------- #
    box = card(slide, CONTENT_X, BAND_Y, left_w, CARD_H, tone="plain", pad="md")
    cur = float(box["cy"])
    title = str(chart_spec.get("title", "") or "")
    note = str(chart_spec.get("note", "") or "")
    note_h = 26.0 if note else 0.0
    if title:
        used = _text(slide, box["cx"], cur, float(box["cw"]), 30, title,
                     token="card_title", size=16, color="navy", bold=True, line_spacing=1.25)
        cur += used["h"] + 8.0
    avail = (float(box["cy"]) + float(box["ch"]) - note_h - 6.0) - cur
    chart_h = chart_height(chart_spec, max(120.0, avail))
    explicit = _num(chart_spec.get("height"), 0.0)
    if explicit > 0:
        chart_h = max(120.0, min(explicit, max(120.0, avail)))
    add_chart(slide, float(box["cx"]), cur, float(box["cw"]), chart_h, chart_spec)
    if note:
        _footnote(slide, float(box["cx"]), float(box["cy"]) + float(box["ch"]) - 18.0,
                  float(box["cw"]), note, size=11.5, color="t3")

    # -- right: KPI cards + navy conclusion ------------------------------- #
    # One budget pass over the whole column: every block gets at least its
    # natural height, the navy conclusion takes the leftover (never less than
    # its text needs), and nothing can overlap the block below it.  Three KPIs
    # become 1 + 2 so a number never shrinks into an unreadable slot.
    NAV_MIN, NAV_MAX = 96.0, 150.0
    if kpis:
        n = len(kpis)
        if n >= 3:
            head_h = 124.0
            tail_h = 108.0
            placements = [(right_x, BAND_Y, right_w, head_h)]
            half = (right_w - GAP) / 2.0
            for j in range(min(2, n - 1)):
                placements.append((right_x + j * (half + GAP), BAND_Y + head_h + GAP,
                                   half, tail_h))
            rows_h = [head_h, tail_h]
        else:
            slot_h = 124.0 if n == 1 else 112.0
            placements = [(right_x, BAND_Y + i * (slot_h + GAP), right_w, slot_h)
                          for i in range(n)]
            rows_h = [slot_h] * n
    else:
        placements = []
        rows_h = []

    card_inputs = [c for c in cards if isinstance(c, dict)]
    kpi_need = sum(rows_h) + GAP * (len(rows_h) - 1) if rows_h else 0.0
    gaps = (GAP if rows_h else 0.0) + (GAP if card_inputs else 0.0) + GAP
    # Reading cards are sized to their own text, not to a fixed slot: giving them
    # a slot and hoping the text fits is what makes a body spill past the card.
    card_slot = 0.0
    if card_inputs:
        exact = (CARD_H - kpi_need - gaps - NAV_MIN) / len(card_inputs)
        card_slot = max(72.0, min(112.0, exact))
    used = kpi_need + (GAP if rows_h and card_inputs else 0.0) + card_slot * len(card_inputs) \
        + GAP * max(0, len(card_inputs) - 1)
    nav_h = max(NAV_MIN, min(NAV_MAX, CARD_H - used - GAP))

    for item, (cx, cy, cw, chh) in zip(kpis, placements):
        kbox = card(slide, cx, cy, cw, chh, tone="tint", pad="sm")
        _kpi(slide, float(kbox["cx"]), float(kbox["cy"]), float(kbox["cw"]),
             float(kbox["ch"]), item.get("value", ""),
             label=str(item.get("label", "") or ""),
             note=str(item.get("note", "") or ""),
             unit=(None if item.get("unit") in (None, "") else str(item.get("unit"))),
             tone=str(item.get("tone", "") or ""), size=None)

    cy = BAND_Y + kpi_need + (GAP if rows_h else 0.0)
    for item in card_inputs:
        cbox = card(slide, right_x, cy, right_w, card_slot,
                    tone=str(item.get("tone") or "plain"), pad="sm")
        card_head(slide, cbox, title=str(item.get("title", "") or ""),
                  body=str(item.get("body", "") or ""), items=_list(item.get("items")),
                  title_size=16.0, body_size=13.0, item_size=13.0)
        cy += card_slot + GAP

    nav_y = BAND_Y + CARD_H - nav_h
    takeaway(slide, right_x, nav_y, right_w, nav_h,
             str(take.get("text", "") or ""), label=str(take.get("label", "") or "IV · 结论"),
             tone="primary", size=14.0)


# --------------------------------------------------------------------------- #
# 07 - split_cards
# --------------------------------------------------------------------------- #


def render_split_cards(slide: Shape, page: Any, ctx: Any) -> None:
    """Two comparison cards with mirrored top accent bars (mint / light)."""
    left = _dict(page.need("left"))
    right = _dict(page.need("right"))
    ratio = _clamp(page.get("ratio", 0.56), 0.45, 0.62, 0.56)

    left_w = (CONTENT_W - GAP) * ratio
    right_x = CONTENT_X + left_w + GAP
    right_w = CONTENT_W - left_w - GAP

    left_box = card(slide, CONTENT_X, BAND_Y, left_w, CARD_H, tone="accent",
                    accent="teal", accent_side="top", accent_w=6.0, pad="md")
    card_head(slide, left_box, chip=_chip_text(left.get("chip")),
              chip_en=str(left.get("chip_en", "") or ""),
              title=str(left.get("title", "") or ""),
              body=str(left.get("body", "") or ""),
              items=_list(left.get("items")),
              footer=str(left.get("footer", "") or ""),
              title_size=18.0, body_size=14.0, item_size=14.0)

    right_box = card(slide, right_x, BAND_Y, right_w, CARD_H, tone="tint",
                     accent="brick", accent_side="top", accent_w=6.0, pad="md")
    card_head(slide, right_box, chip=_chip_text(right.get("chip")),
              chip_en=str(right.get("chip_en", "") or ""),
              title=str(right.get("title", "") or ""),
              body=str(right.get("body", "") or ""),
              items=_list(right.get("items")),
              footer=str(right.get("footer", "") or ""),
              title_size=18.0, body_size=14.0, item_size=14.0)


# --------------------------------------------------------------------------- #
# 08 - concept_flow
# --------------------------------------------------------------------------- #


def _concept_card(slide: Shape, x: float, y: float, w: float, h: float,
                  data: Dict[str, Any], *, accent: str, tone: str = "plain") -> Dict[str, Any]:
    """One side of a concept flow, with a divider above its bullet list."""
    box = card(slide, x, y, w, h, tone=tone, accent=accent, accent_side="left",
               accent_w=5.0, pad="md")
    cur = float(box["cy"])
    title = str(data.get("title", "") or "")
    body = str(data.get("body", "") or "")
    items = _list(data.get("items"))
    if title:
        used = _text(slide, box["cx"], cur, float(box["cw"]), 44,
                     truncate(title, 18, float(box["cw"]), True),
                     token="card_title", size=18, color="navy", bold=True, line_spacing=1.25)
        cur += used["h"] + 8.0
    if body:
        size = 14.0
        used = _text(slide, box["cx"], cur, float(box["cw"]), 90, body,
                     token="card_body", size=size, color="t2", line_spacing=1.45)
        cur += used["h"] + 10.0
    if items and cur < float(box["cy"]) + float(box["ch"]) - 30.0:
        hairline(slide, float(box["cx"]), cur, float(box["cw"]), color="line")
        cur += 10.0
        _bullets(slide, float(box["cx"]), cur, float(box["cw"]),
                 float(box["cy"]) + float(box["ch"]) - cur, items,
                 size=13.5, color="t2", mark="▪", gap=7.0,
                 mark_color="white" if box.get("fill") == "navy" else None)
    return box


def render_concept_flow(slide: Shape, page: Any, ctx: Any) -> None:
    """Conceptual framework: left construct -> mediating arrow -> right construct."""
    left = _dict(page.need("left"))
    right = _dict(page.need("right"))
    center = _dict(page.need("center"))
    take = str(page.get("takeaway", "") or "")

    take_h = 42.0 if take else 0.0
    cards_h = CARD_H - (take_h + 14.0 if take else 0.0)
    left_x, left_w = CONTENT_X, 580.0
    center_x, center_w = 625.0, 30.0
    right_x = 660.0
    right_w = CONTENT_R - right_x

    _concept_card(slide, left_x, BAND_Y, left_w, cards_h, left, accent="teal")
    _concept_card(slide, right_x, BAND_Y, right_w, cards_h, right, accent="navy", tone="tint")

    # The mediator marker: label and note above the arrow, arrow on the row centre.
    mid_y = BAND_Y + cards_h / 2.0
    label = str(center.get("label", "") or "")
    note = str(center.get("note", "") or "")
    lx = center_x - (120.0 - center_w) / 2.0
    if label:
        _text(slide, lx, mid_y - 54.0, 120.0, 24,
              truncate(label, 14, 120.0, True), token="card_title_sm",
              size=14, color="navy", bold=True, align="center", line_spacing=1.15)
    if note:
        _text(slide, lx, mid_y - 32.0, 120.0, 20,
              truncate(note, 11.5, 120.0, False), token="caption", size=11.5,
              color="t3", align="center", line_spacing=1.1)
    add_arrow(slide, center_x + 2.0, mid_y, center_x + center_w - 2.0, mid_y,
              color="teal", w=2.0)

    if take:
        takeaway(slide, CONTENT_X, BAND_Y + cards_h + 14.0, CONTENT_W, take_h, take,
                 label="", tone="primary", size=13.5, pad=(8.0, 18.0, 8.0, 18.0))


# --------------------------------------------------------------------------- #
# 09 - matrix2x2
# --------------------------------------------------------------------------- #


def render_matrix2x2(slide: Shape, page: Any, ctx: Any) -> None:
    """2x2 mechanism matrix with an explanatory aside on the left."""
    aside = _dict(page.need("aside"))
    quadrants = [q for q in _list(page.need("quadrants")) if isinstance(q, dict)]
    center_label = str(page.get("center_label", "") or "")

    aside_w = 340.0
    box = card(slide, CONTENT_X, BAND_Y, aside_w, 430.0, tone="tint", pad="md")
    cur = float(box["cy"])
    title = str(aside.get("title", "") or "")
    body = str(aside.get("body", "") or "")
    items = _list(aside.get("items"))
    axes = _dict(aside.get("axes"))
    if title:
        used = _text(slide, box["cx"], cur, float(box["cw"]), 50,
                     truncate(title, 18, float(box["cw"]), True),
                     token="card_title", size=18, color="navy", bold=True, line_spacing=1.25)
        cur += used["h"] + 8.0
    if body:
        used = _text(slide, box["cx"], cur, float(box["cw"]), 80, body,
                     token="card_body", size=13.5, color="t2", line_spacing=1.45)
        cur += used["h"] + 10.0
    if items:
        room = float(box["cy"]) + float(box["ch"]) - 34.0 - cur
        if room > 40.0:
            _bullets(slide, float(box["cx"]), cur, float(box["cw"]), room, items,
                     size=13.0, color="t2", gap=6.0)
    axis_bits = [b for b in (str(axes.get("y", "") or ""), str(axes.get("x", "") or "")) if b]
    if axis_bits:
        rect(slide, float(box["cx"]), float(box["cy"]) + float(box["ch"]) - 26.0,
             float(box["cw"]), 1, fill="line")
        _text(slide, float(box["cx"]), float(box["cy"]) + float(box["ch"]) - 20.0,
              float(box["cw"]), 18,
              truncate("  ·  ".join(axis_bits), 11.5, float(box["cw"]), False),
              token="caption", size=11.5, color="t3", line_spacing=1.1)

    matrix_grid(slide, 400.0, BAND_Y, 840.0, 400.0, quadrants,
                gap=GAP, center_label=center_label, center_dot=20.0)


# --------------------------------------------------------------------------- #
# 10 - data_table
# --------------------------------------------------------------------------- #


def render_data_table(slide: Shape, page: Any, ctx: Any) -> None:
    """Data table filling the content width, with a caption underneath."""
    columns = _list(page.need("columns"))
    rows = [r for r in _list(page.need("rows"))]
    caption = str(page.get("caption", "") or "")
    highlight_col = int(_num(page.get("highlight_col", -1), -1))
    first_col_bold = bool(page.get("first_col_bold", True))

    nrows = max(1, len(rows))
    head_h = 42.0
    caption_h = 22.0
    # Guide row height: 44-52px.  Rows are capped there and the whole table (plus
    # its caption) is centred in the content band, so a short table never drifts
    # to the top edge or grows into oversized poster rows.
    row_h = min(52.0, max(44.0, 430.0 / nrows))
    body_rows = [list(r) if isinstance(r, (list, tuple)) else [r] for r in rows]
    table_h = head_h + nrows * row_h + caption_h + 8.0
    top = BAND_Y + max(0.0, (CARD_H - table_h) / 2.0)
    result = _table(slide, CONTENT_X, top, CONTENT_W, columns, body_rows,
                    row_h=row_h, head_h=head_h, highlight_col=highlight_col,
                    first_col_bold=first_col_bold)
    if caption:
        _footnote(slide, CONTENT_X, result["bottom"] + 12.0, CONTENT_W, caption,
                  size=11.5, color="t3")


# --------------------------------------------------------------------------- #
# 11 - key_findings
# --------------------------------------------------------------------------- #


def render_key_findings(slide: Shape, page: Any, ctx: Any) -> None:
    """A navy findings banner over one wide card and two flexible cards."""
    banner = _dict(page.need("banner"))
    cards = [c for c in _list(page.need("cards")) if isinstance(c, dict)][:3]
    ratio = _clamp(page.get("cards_ratio", 0.46), 0.4, 0.56, 0.46)

    stat_banner(slide, CONTENT_X, BAND_Y, CONTENT_W, 110.0,
                _list(banner.get("figures")),
                heading=str(banner.get("heading", "") or ""),
                note=str(banner.get("note", "") or ""),
                value_size=44.0)

    y = BAND_Y + 110.0 + GAP
    h = FOOT_Y - y
    if not cards:
        return
    rest = cards[1:]
    first_w = (CONTENT_W - GAP) * ratio if rest else CONTENT_W
    first = card(slide, CONTENT_X, y, first_w, h,
                 tone=str(cards[0].get("tone") or "plain"), pad="md")
    card_head(slide, first, title=str(cards[0].get("title", "") or ""),
              body=str(cards[0].get("body", "") or ""), title_size=18.0,
              body_size=14.0, item_size=13.5)
    if not rest:
        return
    rx = CONTENT_X + first_w + GAP
    rw = CONTENT_R - rx
    n = len(rest)
    each = (rw - GAP * (n - 1)) / n
    for i, item in enumerate(rest):
        cx = rx + i * (each + GAP)
        box = card(slide, cx, y, each, h,
                   tone=str(item.get("tone") or ("tint" if i == 0 else "accent")), pad="md")
        card_head(slide, box, title=str(item.get("title", "") or ""),
                  body=str(item.get("body", "") or ""), items=_list(item.get("items")),
                  title_size=16.0, body_size=13.5, item_size=13.0)


# --------------------------------------------------------------------------- #
# 12 - closing
# --------------------------------------------------------------------------- #


def render_closing(slide: Shape, page: Any, ctx: Any) -> None:
    """Closing page: quotation block, limitations / future cards, thanks strip."""
    quote = _dict(page.need("quote"))
    panels = [p for p in _list(page.need("panels")) if isinstance(p, dict)][:3]
    thanks = str(page.get("thanks", "") or "")
    meta = _meta(ctx)

    rect(slide, 0, 0, CANVAS_W, 100, fill="navy")
    rect(slide, 32, 30, 8, 8, fill="teal")
    title = str(page.title or page.get("title", "")
                or getattr(meta, "kicker", "") or "总结与展望")
    _text(slide, 40, 26, 900, 30, truncate(title, 20, 900, True),
          token="card_title", size=20, color="white", bold=True)
    series = str(page.get("series", "") or getattr(meta, "journal", "") or "")
    if series:
        _text(slide, 940, 30, 300, 22, truncate(series, 13, 300, False),
              token="footer", size=13, color="white", align="right")
    rect(slide, 0, 100, 6, 380, fill="teal")

    # Quotation block.
    qbox = card(slide, CONTENT_X, 140.0, CONTENT_W, 190.0, tone="accent",
                accent="teal", accent_side="left", accent_w=6.0, pad=(24.0, 28.0, 22.0, 34.0))
    qtext = str(quote.get("text", "") or "")
    qsource = str(quote.get("source", "") or "")
    size = 22.0
    while size > 16.0 and estimate_height(
            [_para(qtext, style_of("quote", size=size, color="navy"), line_spacing=1.4)],
            float(qbox["cw"])) > float(qbox["ch"]) - (18.0 if qsource else 0.0):
        size -= 0.5
    _text(slide, float(qbox["cx"]), float(qbox["cy"]), float(qbox["cw"]), 120, qtext,
          token="quote", size=size, color="navy", bold=True, line_spacing=1.4)
    if qsource:
        _text(slide, float(qbox["cx"]), float(qbox["cy"]) + float(qbox["ch"]) - 18.0,
              float(qbox["cw"]), 18, "— " + truncate(qsource, 12, float(qbox["cw"]) - 20.0, False),
              token="caption", size=12, color="t3", line_spacing=1.1)

    # Limitation / future panels.
    y = 350.0
    h = 270.0
    if panels:
        n = len(panels)
        gap = GAP
        first_w = CONTENT_W if n == 1 else 560.0
        rest_w = 0.0 if n == 1 else (CONTENT_W - first_w - gap * (n - 1)) / (n - 1)
        widths = [first_w] + [rest_w] * (n - 1)
        x = CONTENT_X
        for i, item in enumerate(panels):
            w = widths[i] if i < len(widths) else widths[-1]
            tone = str(item.get("tone") or ("plain" if i == 0 else "primary"))
            box = card(slide, x, y, w, h, tone=tone, pad="md")
            card_head(slide, box, title=str(item.get("title", "") or ""),
                      body=str(item.get("body", "") or ""), items=_list(item.get("items")),
                      title_size=18.0, body_size=14.0, item_size=13.5)
            x += w + gap

    # Thanks strip + closing colour band.
    strip_y = 648.0
    rect(slide, CONTENT_X, strip_y, CONTENT_W, 32.0, fill="mint")
    _text(slide, CONTENT_X + 16.0, strip_y, 60.0, 32.0, "致谢", token="caption",
          size=12, color="grayblue", bold=True, anchor="middle", line_spacing=1.05)
    _text(slide, CONTENT_X + 76.0, strip_y, CONTENT_W - 92.0, 32.0,
          thanks or "Thanks for your attention · 欢迎批评指正", token="card_body",
          size=14, color="navy", align="left", anchor="middle", line_spacing=1.05)
    rect(slide, 0, 712, CANVAS_W, 8, fill="navy")


# --------------------------------------------------------------------------- #
# Registry and dispatch
# --------------------------------------------------------------------------- #


def _unknown(layout: str) -> None:
    """Raise the house-standard error for an unmapped layout name."""
    raise KeyError(
        f"unknown layout {layout!r}; known layouts: {', '.join(sorted(RENDERERS))}"
    )


#: Layout name (from :data:`deepocean.schema.LAYOUTS`) -> renderer callable.
RENDERERS: Dict[str, Callable[[Shape, Any, Any], None]] = {
    "cover": render_cover,
    "two_column": render_two_column,
    "big_number": render_big_number,
    "experiment_design": render_experiment_design,
    "roadmap": render_roadmap,
    "chart_insight": render_chart_insight,
    "split_cards": render_split_cards,
    "concept_flow": render_concept_flow,
    "matrix2x2": render_matrix2x2,
    "data_table": render_data_table,
    "key_findings": render_key_findings,
    "closing": render_closing,
}


def render(layout: str, slide: Shape, page: Any, ctx: Any) -> None:
    """Render one page with the renderer registered for ``layout``.

    Args:
        layout: A layout name or schema alias (e.g. ``"chart"``).
        slide: Slide to draw on.
        page: The :class:`deepocean.spec.Page` being drawn.
        ctx: The render context.

    Raises:
        KeyError: When the layout is neither in the schema nor in
            :data:`RENDERERS`.
    """
    try:
        name = schema.resolve(layout)
    except KeyError:
        _unknown(str(layout))
        return  # pragma: no cover - _unknown always raises
    fn = RENDERERS.get(name)
    if fn is None:
        _unknown(str(layout))
    fn(slide, page, ctx)


def build_page(slide: Shape, page: Any, ctx: Any) -> None:
    """Draw one page: shared chrome first, then the layout-specific content.

    Args:
        slide: The slide to draw on (already added to the presentation).
        page: A :class:`deepocean.spec.Page`.
        ctx: The render context carrying deck, index and total.

    Raises:
        KeyError: For an unknown layout name.
        deepocean.spec.SpecError: When a required layout field is missing.
    """
    layout = str(getattr(page, "layout", "") or "")
    if schema.needs_chrome(layout):
        master(slide, page, ctx)
    render(layout, slide, page, ctx)
