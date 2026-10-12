# -*- coding: utf-8 -*-
"""Reusable Deep Ocean components — the vocabulary every layout is built from.

A component is a small, self-contained drawing routine that speaks **px on the
1280 x 720 canvas** and returns geometry the caller can stack further content
into.  Layouts in :mod:`deepocean.layouts` never draw a card, a KPI or a table
by hand; they compose the pieces below, which keeps the deck inside the safe
margins and inside the palette.

The shared chrome
-----------------
:func:`master` draws the three bands every content page shares (A top bar,
B title block, D footer) so that no layout can drift away from the guide.

Conversions
-----------
python-pptx stores paragraph spacing in points while this module is authored in
design pixels, so :func:`_pt` bridges the two exactly like :mod:`deepocean.units`
does for font sizes.

All colours are addressed by palette key (see :mod:`deepocean.tokens`) and
resolved through :func:`deepocean.primitives.rgb`; a raw hex value never
appears in this file.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from pptx.enum.text import MSO_ANCHOR, PP_ALIGN

from . import tokens
from .primitives import hexof, measure_text, oval, rect, rgb, truncate, wrap_lines

__all__ = [
    "CARD_PAD", "PAGE_RECORDS",
    "master", "card", "card_head", "kpi", "takeaway", "process_steps",
    "compare_pair", "matrix_grid", "table", "stat_banner", "chip", "bullets",
    "footnote",
]

Shape = Any

# --------------------------------------------------------------------------- #
# Geometry constants (px, origin top-left, canvas 1280 x 720)
# --------------------------------------------------------------------------- #

#: Distance to keep a stroke inside its nominal box without bleeding past a margin.
STROKE_INSET = 1.0

#: Card padding ``(top, right, bottom, left)`` per size, from the style guide.
CARD_PAD: Dict[str, Tuple[float, float, float, float]] = {
    "sm": (14.0, 16.0, 14.0, 16.0),
    "md": (18.0, 20.0, 18.0, 20.0),
    "lg": (24.0, 28.0, 20.0, 28.0),
}

_TONE_STYLES: Dict[str, Dict[str, Any]] = {
    "plain":   {"fill": "white", "line": "line",  "accent": None,       "ink": "t1",    "sub": "t2"},
    "tint":    {"fill": "light", "line": None,    "accent": None,       "ink": "t1",    "sub": "t2"},
    "accent":  {"fill": "mint",  "line": None,    "accent": "teal",     "ink": "t1",    "sub": "t2"},
    "primary": {"fill": "navy",  "line": None,    "accent": None,       "ink": "white", "sub": "white"},
    "neutral": {"fill": "light", "line": None,    "accent": "grayblue", "ink": "t1",    "sub": "t2"},
    "danger":  {"fill": "pink",  "line": None,    "accent": "brick",    "ink": "t1",    "sub": "t2"},
}

#: Tone key -> ``(fill key, accent key or None)``; ``alert`` aliases ``danger``.
TONES: Dict[str, Tuple[str, Optional[str]]] = {
    "plain": ("white", "line"),
    "tint": ("light", None),
    "accent": ("mint", "teal"),
    "danger": ("pink", "brick"),
    "alert": ("pink", "brick"),
    "primary": ("navy", None),
    "neutral": ("light", "grayblue"),
    "dark": ("navy", None),
    "muted": ("light", None),
}

#: What :func:`master` drew on the current page, for layouts that want to know.
PAGE_RECORDS: Dict[str, Any] = {}


# --------------------------------------------------------------------------- #
# Small helpers
# --------------------------------------------------------------------------- #


def _pt(px: float) -> float:
    """Design px -> PowerPoint points, keeping a size floor exact.

    Rounded to 0.01pt: a whole-point round would turn the 11px minimum into
    8.25pt (10.99px) and trips the linter's ``T001`` floor.
    """
    return round(float(px) * 0.75, 2)


def _spacing_pt(px: float) -> int:
    """Design px -> whole points for paragraph spacing (pptx stores ints there)."""
    return int(round(float(px) * 0.75))


def _num(value: Optional[float], fallback: float = 0.0) -> float:
    """Coerce a spec value to a usable number (``None`` / ``""`` -> fallback)."""
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return float(fallback)


def _clamp(value: Optional[float], lo: float, hi: float, fallback: float) -> float:
    """Clamp a spec ratio into its documented band."""
    v = _num(value, fallback)
    if v <= 0:
        v = fallback
    return max(lo, min(hi, v))


def _color(key: Optional[str]) -> Optional[str]:
    """Resolve a palette key / role to ``#RRGGBB``, passing ``None`` through."""
    return None if key is None else hexof(str(key))


def _tone_of(name: Optional[str], default: str = "plain") -> str:
    key = str(name or default).strip().lower()
    return key if key in _TONE_STYLES else default


def style_of(token: Any = "card_body", color: Optional[str] = None,
             size: Optional[float] = None, bold: Optional[bool] = None,
             spacing: Optional[float] = None) -> Dict[str, Any]:
    """Resolve a type token (plus overrides) into a run style dict.

    Args:
        token: A :data:`deepocean.tokens.TYPE_SCALE` key or a ``TypeToken``.
        color: Palette key / role overriding the token colour.
        size: Override in design px (converted to pt internally).
        bold: Override the token weight.
        spacing: Letter spacing in px.

    Returns:
        A dict accepted by the private paragraph renderer.
    """
    base = tokens.type_token(token) if isinstance(token, str) else token
    return {
        "size": _pt(base.px) if size is None else _pt(size),
        "bold": base.bold if bold is None else bool(bold),
        "italic": False,
        "color": _color(color if color is not None else base.color),
        "spacing": base.letter_spacing if spacing is None else spacing,
    }


def line_boxes(paras_px: Sequence[Dict[str, Any]], wrap_w: float) -> int:
    """Total wrapped lines, counted with the frozen :func:`primitives.wrap_lines`.

    Using the primitives' own line breaking keeps this module's box heights in
    step with :mod:`deepocean.check`, which measures overflow the same way.
    """
    total = 0
    for spec in paras_px:
        runs = spec.get("runs") or []
        if not runs:
            continue
        text = "".join(str(r.get("text", "")) for r in runs)
        st = runs[0].get("style", {})
        # ``style["size"]`` is points (what python-pptx stores); wrap_lines wants px.
        size_px = float(st.get("size", 10.5)) / 0.75
        total += len(wrap_lines(text, size_px, max(1.0, wrap_w), bool(st.get("bold"))))
    return total


def text_box_height(paras_px: Sequence[Dict[str, Any]], wrap_w: float) -> float:
    """Height (px) for a text box: generous enough for every renderer.

    A rendered line of slide text occupies about ``1.5 * size`` — the model
    :mod:`deepocean.check` applies in its overflow rule — while
    :func:`estimate_height` tracks the tighter geometric estimate used to lay
    blocks out.  Taking the larger of the two means a box is never flagged as
    overflowing and never clips its ink.
    """
    geo = estimate_height(paras_px, wrap_w) * 1.06 + 2.0
    needed = 0.0
    for spec in paras_px:
        runs = spec.get("runs") or []
        if not runs:
            continue
        text = "".join(str(r.get("text", "")) for r in runs)
        st = runs[0].get("style", {})
        # ``style["size"]`` is points (what python-pptx stores); wrap_lines wants px.
        size_px = float(st.get("size", 10.5)) / 0.75
        lines = len(wrap_lines(text, size_px, max(1.0, wrap_w), bool(st.get("bold"))))
        needed += (float(spec.get("space_before") or 0.0)
                   + lines * size_px * 1.50
                   + float(spec.get("space_after") or 0.0))
    return max(16.0, geo, needed)


def _render_paras(slide: Shape, x: float, y: float, w: float, paras_px: List[Dict[str, Any]],
                  anchor: str = "top", wrap: bool = True) -> None:
    """Write pre-built paragraph dicts into a text box and measure real heights.

    Spacing values in ``paras_px`` are design px and are converted to points
    here, which is what python-pptx stores.
    """
    h = text_box_height(paras_px, w)
    tb, tf = _textbox(slide, x, y, w, max(16.0, h), anchor=anchor, wrap=wrap)
    first = True
    for spec in paras_px:
        para = tf.paragraphs[0] if first else tf.add_paragraph()
        first = False
        align = spec.get("align")
        if align:
            para.alignment = {"left": PP_ALIGN.LEFT, "center": PP_ALIGN.CENTER,
                              "centre": PP_ALIGN.CENTER, "right": PP_ALIGN.RIGHT,
                              "justify": PP_ALIGN.JUSTIFY}.get(align, PP_ALIGN.LEFT)
        if spec.get("space_before"):
            para.space_before = _spacing_pt(spec["space_before"])
        if spec.get("space_after"):
            para.space_after = _spacing_pt(spec["space_after"])
        # Clamp to a sane band: paragraph specs carry a multiplier here, and a
        # value under 1.0 would make the rendered lines collide.
        para.line_spacing = max(0.85, min(2.6, float(spec.get("line_spacing") or 1.2)))
        for run_spec in spec.get("runs", []):
            run = para.add_run()
            _write(run, str(run_spec.get("text", "")), run_spec.get("style", {}))


def _textbox(slide: Shape, x: float, y: float, w: float, h: float,
             anchor: str = "top", wrap: bool = True) -> Tuple[Shape, Shape]:
    """Add a fully un-padded text box (px), returning ``(shape, text_frame)``."""
    from pptx.util import Emu

    from .units import px_to_emu

    tb = slide.shapes.add_textbox(Emu(px_to_emu(x)), Emu(px_to_emu(y)),
                                  Emu(px_to_emu(w)), Emu(px_to_emu(max(2.0, h))))
    tf = tb.text_frame
    tf.word_wrap = bool(wrap)
    tf.margin_left = Emu(0)
    tf.margin_right = Emu(0)
    tf.margin_top = Emu(0)
    tf.margin_bottom = Emu(0)
    tf.vertical_anchor = {"top": MSO_ANCHOR.TOP, "middle": MSO_ANCHOR.MIDDLE,
                          "center": MSO_ANCHOR.MIDDLE,
                          "bottom": MSO_ANCHOR.BOTTOM}.get(anchor, MSO_ANCHOR.TOP)
    return tb, tf


def _fonts() -> Tuple[str, str]:
    """The deck-wide Latin / CJK pair, honouring ``primitives.set_fonts``.

    ``deepocean.build`` calls ``set_fonts`` from ``meta.fonts``; falling back to
    the PowerPoint-safe stack keeps this module usable without a build step.
    """
    latin = tokens.FONTS.get("ppt_latin") or tokens.FONTS["latin"][0]
    cjk = tokens.FONTS.get("ppt_cjk") or tokens.FONTS["cjk"][0]
    try:
        from .primitives import default_fonts

        return default_fonts()
    except (ImportError, AttributeError, TypeError):  # pragma: no cover - defensive
        return str(latin), str(cjk)


def _write(run: Shape, text: str, st: Dict[str, Any]) -> None:
    """Apply a style dict to one python-pptx run (px -> pt at the boundary)."""
    from pptx.oxml.ns import qn
    from pptx.util import Pt

    run.text = text
    font = run.font
    font.size = Pt(st.get("size", 10.5))
    font.bold = bool(st.get("bold", False))
    font.italic = bool(st.get("italic", False))
    if st.get("color"):
        font.color.rgb = rgb(str(st["color"]))
    default_latin, default_cjk = _fonts()
    latin = st.get("font_latin") or default_latin
    cjk = st.get("font_cjk") or default_cjk
    font.name = latin
    rPr = run._r.get_or_add_rPr()
    ea = rPr.find(qn("a:ea"))
    if ea is None:
        ea = rPr.makeelement(qn("a:ea"), {})
        rPr.append(ea)
    ea.set("typeface", cjk)
    cs = rPr.find(qn("a:cs"))
    if cs is None:
        cs = rPr.makeelement(qn("a:cs"), {})
        rPr.append(cs)
    cs.set("typeface", latin)
    spacing = st.get("spacing")
    if spacing:
        rPr.set("spc", str(int(round(float(spacing) * 75))))  # px -> 1/100 pt


def _para(text: str, st: Dict[str, Any], align: Optional[str] = None,
          space_before: float = 0.0, space_after: float = 0.0,
          line_spacing: Optional[float] = None) -> Dict[str, Any]:
    return {"runs": [{"text": text, "style": st}], "align": align,
            "space_before": space_before, "space_after": space_after,
            "line_spacing": line_spacing or 1.2}


def text_style_pt(key: str, **kw: Any) -> Dict[str, Any]:
    """Token style in points — convenient when sizing by measurement."""
    return style_of(key, **kw)


#: Per-line leading factor shared by measurement and layout.  A rendered line of
#: PowerPoint text occupies about ``1.5 * size`` regardless of the requested
#: line spacing (that is also the model :mod:`deepocean.check` uses for its
#: overflow rule), so reserving ``line_spacing * 1.44`` keeps every box inside
#: the linter's 15% slack while staying taller than the ink really is.
LEADING = 1.44


def estimate_height(paras_px: Sequence[Dict[str, Any]], wrap_w: float) -> float:
    """Estimated rendered height (px) of paragraph dicts at wrap width ``wrap_w``.

    Accounts for per-paragraph ``space_before`` / ``space_after`` and for the
    leading that real text engines add beyond ``size * line_height``.
    """
    total = 0.0
    for spec in paras_px:
        runs = spec.get("runs") or []
        if not runs:
            continue
        text = "".join(str(r.get("text", "")) for r in runs)
        st = runs[0].get("style", {})
        # ``style["size"]`` is points (what python-pptx stores); wrap_lines wants px.
        size_px = float(st.get("size", 10.5)) / 0.75
        line_h = float(spec.get("line_spacing") or 1.2)
        lines = _wrap_count(text, size_px, wrap_w, bool(st.get("bold")))
        total += float(spec.get("space_before") or 0.0)
        total += lines * size_px * line_h * LEADING + size_px * 0.06
        total += float(spec.get("space_after") or 0.0)
    return total


def _wrap_count(text: str, size_px: float, width_px: float, bold: bool = False,
                max_lines: int = 24) -> int:
    """Line count using the frozen :func:`primitives.wrap_lines` model.

    CJK has no spaces, so a space-split counts a whole Chinese paragraph as one
    line and every block downstream is laid out a line too high — the classic
    "body text collides with its bullets" bug.  Delegating to
    :mod:`deepocean.primitives` keeps this module, the PPTX renderer and
    :mod:`deepocean.check`'s overflow rule on exactly the same ruler.
    """
    if not text:
        return 1
    return min(max(1, len(wrap_lines(text, size_px, max(1.0, width_px), bold))), max_lines)


def gap_px(size: str = "md") -> float:
    """The standard gutter between blocks (px)."""
    return {"sm": 8.0, "md": 12.0, "lg": 20.0}.get(size, 12.0)


# --------------------------------------------------------------------------- #
# Shared chrome — band A + band B + band D
# --------------------------------------------------------------------------- #


def master(slide: Shape, page: Any, ctx: Any) -> Dict[str, Any]:
    """Draw the shared page chrome: top bar, title block and footer.

    Content pages all share the same four bands so that a deck reads as one
    document.  Cover and closing pages draw their own chrome (see
    :func:`deepocean.schema.needs_chrome`).

    Args:
        slide: The python-pptx slide to draw on.
        page: A :class:`deepocean.spec.Page`.
        ctx: The layout context (:class:`deepocean.primitives.Ctx`).

    Returns:
        A record describing the drawn chrome (band extents, resolved note) that
        is also stored in :data:`PAGE_RECORDS` for interested layouts.
    """
    meta = getattr(getattr(ctx, "deck", None), "meta", None)
    journal = str(page.get("journal", "") or getattr(meta, "journal", "") or "")
    title = str(page.title or page.get("title", "") or "")
    title_en = str(page.title_en or page.get("title_en", "") or "")
    kicker = str(page.kicker or page.get("kicker", "") or "")
    subtitle = str(page.subtitle or page.get("subtitle", "") or "")
    note = ""
    try:
        note = str(ctx.note() or "")
    except AttributeError:  # pragma: no cover - defensive
        note = ""

    # -- band A: navy top bar --------------------------------------------- #
    rect(slide, 0, 0, 1280, 60, fill="navy")
    rect(slide, 32, 26, 8, 8, fill="teal")
    if journal:
        _render_paras(slide, 940, 22, 300,
                      [_para(truncate(journal, 13, 300, False), style_of("footer", color="white", size=13),
                             align="right", line_spacing=1.15)])

    # -- band B: kicker / title / optional English subtitle / divider ------ #
    if kicker:
        _render_paras(slide, 40, 76, 1080,
                      [_para(truncate(kicker, 14, 1080, True).upper(),
                             style_of("kicker", spacing=2.5), line_spacing=1.1)])
    if title:
        size = 30.0
        while size > 22.0 and _wrap_count(title, size, 1200, True) > 1:
            size -= 1.0
        _render_paras(slide, 40, 100, 1200,
                      [_para(title, style_of("page_title", size=size, color="navy"),
                             line_spacing=1.18)])
    if title_en or subtitle:
        _render_paras(slide, 40, 140, 1200,
                      [_para(truncate(title_en or subtitle, 15, 1200, False),
                             style_of("page_subtitle", color="grayblue"), line_spacing=1.2)])
    rect(slide, 40, 168, 1200, 1, fill="line")

    # -- band D: hairline rule + source note + page number ---------------- #
    rect(slide, 40, 680, 1200, 1, fill="line")
    if note:
        _render_paras(slide, 40, 688, 900,
                      [_para(truncate(note, 12, 900, False), style_of("footer", color="t3"),
                             line_spacing=1.1)])
    index = int(getattr(ctx, "index", 1) or 1)
    total = int(getattr(ctx, "total", 1) or 1)
    _render_paras(slide, 1040, 688, 200,
                  [_para(f"{index:02d} / {total:02d}", style_of("page_number", color="navy"),
                         align="right", line_spacing=1.1)])

    record = {
        "top_bar": (0.0, 0.0, 1280.0, 60.0),
        "title_block": (40.0, 72.0, 1200.0, 96.0),
        "content_y": 184.0,
        "divider_y": 168.0,
        "footer_y": 680.0,
        "note": note,
        "journal": journal,
    }
    PAGE_RECORDS.clear()
    PAGE_RECORDS.update(record)
    return record


# --------------------------------------------------------------------------- #
# Cards
# --------------------------------------------------------------------------- #


def card(slide: Shape, x: float, y: float, w: float, h: float, *,
         tone: str = "plain", fill: Optional[str] = None,
         line: Optional[str] = None, line_w: float = 1.0,
         radius: Optional[float] = None,
         accent: Optional[str] = None,
         accent_side: str = "left", accent_w: float = 5.0,
         pad: Any = "md") -> Dict[str, Any]:
    """Draw a card container and report the box its content should use.

    Args:
        slide: Slide to draw on.
        x: Left edge in px.
        y: Top edge in px.
        w: Width in px.
        h: Height in px.
        tone: One of ``plain``/``tint``/``accent``/``danger``/``primary``/
            ``neutral`` (``alert`` aliases ``danger``).  Drives fill + accent.
        fill: Explicit fill override (palette key).
        line: Explicit stroke override; ``None`` keeps the tone default.
        line_w: Stroke width in px.
        radius: Corner radius in px (``None`` = square corners, the guide default).
        accent: Explicit accent colour for the side bar.
        accent_side: ``left`` (default) or ``top``.
        accent_w: Accent bar thickness in px (guide: 5-6).
        pad: Padding preset key (:data:`CARD_PAD`) or explicit
            ``(top, right, bottom, left)`` tuple.

    Returns:
        A box dict: ``x, y, w, h`` (card), ``cx, cy, cw, ch`` (content area),
        ``pad``, ``tone``, ``fill``, ``ink``, ``sub``, ``accent``.
    """
    tone_key = _tone_of(tone)
    preset = _TONE_STYLES[tone_key]
    fill_key = fill if fill is not None else preset["fill"]
    ink = preset["ink"]
    sub = preset["sub"]
    if fill is not None and str(fill).lower() in ("navy", "primary", "danger", "brick"):
        ink = "white"
        sub = "white"
    accent_key = accent if accent is not None else preset["accent"]
    if line is None:
        line_key: Optional[str] = preset["line"]
        if fill is not None and preset["line"] == "line":
            line_key = "line"
    else:
        line_key = line
    if accent_key == "line":
        accent_key = None

    # Accent bar first so its outer edge is never overdrawn by the card body.
    bar = 0.0
    if accent_key:
        bar = float(accent_w or 5.0)
        if accent_side == "top":
            rect(slide, x, y, w, bar, fill=accent_key)
        else:
            rect(slide, x, y, bar, h, fill=accent_key)

    rect(slide, x, y, w, h, fill=fill_key, line=line_key, line_w=line_w, radius=radius)

    pad_box = CARD_PAD.get(pad, CARD_PAD["md"]) if isinstance(pad, str) else tuple(pad)
    top, right, bottom, left = (float(v) for v in pad_box)
    if accent_key and accent_side == "left":
        left += bar
    if accent_key and accent_side == "top":
        top += bar

    return {
        "x": float(x), "y": float(y), "w": float(w), "h": float(h),
        "cx": float(x) + left, "cy": float(y) + top,
        "cw": max(1.0, float(w) - left - right),
        "ch": max(1.0, float(h) - top - bottom),
        "pad": (top, right, bottom, left),
        "tone": tone_key, "fill": fill_key, "ink": ink, "sub": sub,
        "accent": accent_key, "accent_w": bar,
    }


def _as_box(card_obj: Any, slide: Shape, x: Optional[float], y: Optional[float],
            w: Optional[float], h: Optional[float], kw: Dict[str, Any]) -> Dict[str, Any]:
    """Accept either an already-drawn card box or raw coordinates."""
    if isinstance(card_obj, dict) and "cx" in card_obj:
        return card_obj
    if x is None or y is None or w is None or h is None:
        raise ValueError("card_head needs either a card box or x/y/w/h")
    return card(slide, x, y, w, h, **kw)


def card_head(slide: Shape, card_obj: Any = None, *, x: Optional[float] = None,
              y: Optional[float] = None, w: Optional[float] = None,
              h: Optional[float] = None, chip: str = "",
              chip_en: str = "", title: str = "", body: str = "",
              items: Optional[Iterable[Any]] = None, footer: str = "",
              ink: Optional[str] = None, sub: Optional[str] = None,
              title_size: float = 18.0, body_size: float = 14.0,
              item_size: float = 14.0, footer_size: float = 12.0,
              fit: bool = True, mark: str = "▪", chip_text: Optional[str] = None,
              **card_kw: Any) -> Dict[str, Any]:
    """Fill a card with the standard head: chip, title, body, bullets, footer.

    Args:
        slide: Slide to draw on.
        card_obj: A box returned by :func:`card`; when ``None`` the card is
            drawn from ``x``/``y``/``w``/``h`` plus any ``card_kw``.
        chip: Short chip label (e.g. ``"互补"``) drawn in the top-left corner.
        chip_en: Optional secondary chip label next to it (small caps look).
        title: Card title (``card_title`` token).
        body: Explanatory paragraph.
        items: Bullet items — strings or ``(lead, rest)`` pairs.
        footer: Small footer line pinned to the card's bottom edge.
        ink: Text colour override (defaults to the tone's ink).
        sub: Secondary text colour override.
        title_size: Title size in px.
        body_size: Body size in px (never below 13).
        item_size: Bullet size in px.
        footer_size: Footer size in px (never below 11).
        fit: Shrink body text (never below 13px) to keep it inside the card.
        mark: Bullet glyph.
        chip_text: Alias for ``chip`` for callers that shadow the name.

    Returns:
        The card box dict, extended with ``used`` (px of content height used).
    """
    box = _as_box(card_obj, slide, x, y, w, h, card_kw)
    ink_key = ink or box.get("ink", "t1")
    sub_key = sub or box.get("sub", "t2")
    if box.get("fill") == "navy" and ink is None:
        ink_key = "white"
        sub_key = "white"

    cur = float(box["cy"])
    bottom = float(box["cy"]) + float(box["ch"])
    if footer:
        footer = str(footer)

    # Chip row ------------------------------------------------------------- #
    chip_label = str(chip_text if chip_text is not None else chip or "")
    if chip_label:
        chip_h = 20.0
        chip_size = 11.5
        # The pill is sized to its label, never squeezed into a fixed width, so
        # an all-caps Latin tag cannot wrap onto a second line.  The slack covers
        # renderers that fall back to a wider face than the design font.
        want = measure_text(chip_label, chip_size, True) * 1.18 + 30.0
        chip_w = min(max(46.0, want), float(box["cw"]) * 0.58)
        _chip(slide, box["cx"], cur, chip_w, chip_h, chip_label,
              tone="primary" if box.get("fill") == "navy" else "accent",
              fill=str(box.get("fill") or "mint"), size=chip_size)
        if chip_en:
            en_w = max(20.0, float(box["cw"]) - chip_w - 8)
            _render_paras(slide, box["cx"] + chip_w + 8, cur + 2, en_w,
                          [_para(truncate(str(chip_en), 12, en_w, False).upper(),
                                 style_of("caption", color=sub_key if sub_key != "white" else "white",
                                          size=12, spacing=1.2), line_spacing=1.1)])
        cur += chip_h + 10.0

    # Title ---------------------------------------------------------------- #
    if title:
        size = float(title_size)
        while size > 15.0 and _wrap_count(str(title), size, float(box["cw"]), True) > 2:
            size -= 1.0
        paras = [_para(str(title), style_of("card_title", size=size, color=ink_key),
                       line_spacing=1.25)]
        hh = estimate_height(paras, float(box["cw"]))
        _render_paras(slide, box["cx"], cur, float(box["cw"]), paras)
        cur += hh + 8.0

    # Body ----------------------------------------------------------------- #
    body_paras: List[Dict[str, Any]] = []
    if body:
        size = max(13.0, float(body_size))
        # Reserve space for what follows, sized from the real bullet count rather
        # than a worst-case constant: over-reserving shrinks the body for no
        # reason, under-reserving lets it collide with its own bullets.
        reserve = 0.0
        if items:
            n_items = len([it for it in items if it not in (None, "")])
            reserve = min(110.0, max(30.0, n_items * 22.0))
            if float(box["cw"]) < 420.0:
                reserve *= 1.4
        if footer:
            reserve += 22.0
        if float(box["ch"]) < 120.0:
            reserve += 32.0
        budget = bottom - cur - reserve - (12.0 if items else 0.0)
        if fit and budget > 20.0:
            while size > 13.0 and estimate_height(
                    [_para(str(body), style_of("card_body", size=size, color=sub_key),
                          line_spacing=1.45)], float(box["cw"])) > budget:
                size -= 0.5
        body_paras = [_para(str(body), style_of("card_body", size=size, color=sub_key),
                            line_spacing=1.45)]
        hh = estimate_height(body_paras, float(box["cw"]))
        _render_paras(slide, box["cx"], cur, float(box["cw"]), body_paras)
        cur += hh + (16.0 if items else 0.0)

    # Bullets -------------------------------------------------------------- #
    if items:
        room = bottom - cur - (20.0 if footer else 0.0)
        bullets(slide, box["cx"], cur, float(box["cw"]), max(14.0, room),
                items, size=float(item_size), color=sub_key, mark=mark,
                mark_color={"navy": "white", "pink": "brick"}.get(str(box.get("fill")), None))
        cur = max(cur, bottom - (20.0 if footer else 0.0))

    # Footer --------------------------------------------------------------- #
    if footer and footer_size > 0:
        _render_paras(slide, box["cx"], bottom - 16.0, float(box["cw"]),
                      [_para(truncate(footer, footer_size, float(box["cw"]), False),
                             style_of("caption", size=max(11.0, float(footer_size)),
                                      color=sub_key if sub_key == "white" else "t3"),
                             line_spacing=1.1)])

    box["used"] = cur - float(box["cy"])
    return box


# --------------------------------------------------------------------------- #
# Numbers
# --------------------------------------------------------------------------- #


def _number_paras(value: Any, unit: Optional[str], note_above: Optional[str],
                  note_below: Optional[str], size: float, color: str,
                  align: str, ink: Optional[str] = None) -> List[Dict[str, Any]]:
    """Build ``label / value+unit / note`` paragraphs for a big number."""
    sub = ink or "t2"
    out: List[Dict[str, Any]] = []
    if note_above:
        out.append(_para(str(note_above), style_of("kpi_label", color=sub, size=12),
                         align=align, line_spacing=1.15, space_after=6.0))
    if unit:
        # Shrink the unit with the value, but never under the 11px text floor.
        unit_size = max(11.0, size * max(0.45, min(0.6, 11.0 / max(1.0, size))))
        # On a dark card the unit follows the value (white); on paper it is the
        # quieter grayblue so the number keeps the emphasis.
        unit_color = color if color == "white" else "grayblue"
        runs = [
            {"text": str(value), "style": style_of("kpi_value", size=size, color=color)},
            {"text": " " + str(unit), "style": style_of("kpi_value", size=unit_size,
                                                        color=unit_color)},
        ]
        out.append({"runs": runs, "align": align, "space_before": 0.0,
                    "space_after": 4.0, "line_spacing": 1.02})
    else:
        out.append(_para(str(value), style_of("kpi_value", size=size, color=color),
                         align=align, line_spacing=1.02, space_after=4.0))
    if note_below:
        out.append(_para(str(note_below), style_of("kpi_note", color=sub, size=12),
                         align=align, line_spacing=1.2))
    return out


def kpi(slide: Shape, x: float, y: float, w: float, h: float, value: Any,
        label: Optional[str] = None, note: Optional[str] = None, *,
        unit: Optional[str] = None, tone: Optional[str] = None,
        size: Optional[float] = None, color: Optional[str] = None,
        align: str = "left", ink: Optional[str] = None,
        align_v: str = "top") -> Dict[str, Any]:
    """Draw a big-number KPI: label above, value, note below.

    The value shrinks (44 -> .. -> 20px) until the whole block fits ``h``, so a
    compact slot can never push the note out of its own card and onto whatever
    is drawn underneath.

    Args:
        slide: Slide to draw on.
        x, y, w, h: Box in px.
        value: The number or short text to feature.
        label: Label drawn *above* the value (12px grayblue).
        note: Note drawn *below* the value (12px t2).
        unit: Unit suffix rendered smaller next to the value (e.g. ``"%"``).
        tone: ``up``/``positive`` -> teal, ``down``/``negative`` -> brick,
            ``neutral``/``flat`` -> navy.  Wins over ``color`` when given.
        size: Value size in px (auto by slot height when omitted).
        color: Explicit value colour (palette key).
        align: Paragraph alignment, ``left`` or ``center``.
        ink: Override for the label/note colour.
        align_v: ``top`` keeps the block at the box top (used inside cards);
            ``middle`` centres it in the box.

    Returns:
        A dict with the used box (``x, y, w, h``) and the resolved ``size``.
    """
    tone_key = str(tone or "").strip().lower()
    color_key = {
        "up": "teal", "positive": "teal", "pos": "teal", "gain": "teal",
        "down": "brick", "negative": "brick", "neg": "brick", "loss": "brick",
        "neutral": "navy", "flat": "navy",
    }.get(tone_key, color)
    if color_key is None:
        color_key = color
    if color_key is None:
        color_key = "navy"
    anchor = "left" if align == "left" else align
    sub_ink = ink or "t2"
    if color_key == "white" and ink is None:
        sub_ink = "white"

    # Pick the largest value size whose whole block fits the slot, never going
    # below 24px: a KPI number that is too small stops being an anchor.
    size = float(size) if size else (44.0 if h >= 150.0 else 32.0)
    size = min(size, 44.0)
    if w < 150.0:
        size = min(size, 24.0)
    if w < 110.0:
        size = min(size, 22.0)
    floor = 22.0 if w < 110.0 else 24.0
    paras = _number_paras(value, unit, label, note, size, color_key, anchor, sub_ink)
    while size > floor and estimate_height(paras, w) > h - 4.0:
        size -= 2.0
        paras = _number_paras(value, unit, label, note, size, color_key, anchor, sub_ink)
    needed = estimate_height(paras, w)
    if align_v == "middle" and needed < h - 12.0:
        top = y + (h - needed) / 2.0
    else:
        top = y
    _render_paras(slide, x, top, w, paras, anchor="top")
    return {"x": x, "y": y, "w": w, "h": h, "size": size, "used": needed,
            "color": color_key}


def stat_banner(slide: Shape, x: float, y: float, w: float, h: float,
                figures: Sequence[Dict[str, Any]], *,
                heading: str = "", note: str = "",
                value_size: float = 44.0) -> Dict[str, Any]:
    """Draw a full-width navy banner holding 2-4 featured numbers.

    Args:
        slide: Slide to draw on.
        x, y, w, h: Banner box in px.
        figures: ``[{value, unit, label, tone}]``; 2-4 entries.
        heading: Small heading at the banner's left edge.
        note: Optional footnote line under the heading.
        value_size: Value size in px for the banner numbers.

    Returns:
        The banner box dict, extended with the per-figure boxes in ``cells``.
    """
    box = card(slide, x, y, w, h, tone="primary",
               pad=(20.0, 24.0, 18.0, 24.0) if heading else (16.0, 24.0, 16.0, 24.0))
    head_w = 0.0
    if heading:
        head_w = min(float(w) * 0.30, 260.0)
        _render_paras(slide, box["cx"], box["cy"] + max(0.0, (float(h) - 60.0) / 2.0 - 8.0),
                      head_w - 16.0,
                      [_para(heading, style_of("card_title", size=16, color="white"),
                             line_spacing=1.25)]
                      + ([_para(note, style_of("caption", size=11.5, color="white"),
                                line_spacing=1.2, space_before=4.0)] if note else []))
    figs = [f for f in (figures or []) if isinstance(f, dict)][:4]
    if not figs:
        return {"x": box["x"], "y": box["y"], "w": box["w"], "h": box["h"], "cells": []}

    avail = float(box["cw"]) - head_w
    cell_w = avail / len(figs)
    cells: List[Dict[str, Any]] = []
    for i, fig in enumerate(figs):
        cx = box["cx"] + head_w + i * cell_w
        # On the navy banner every figure is white: brick or navy ink would sink
        # into the background (the guide's contrast rule).
        paras = _number_paras(fig.get("value", ""), fig.get("unit"),
                              None, fig.get("label"), value_size,
                              "white", "left", "white")
        needed = estimate_height(paras, cell_w - 16.0)
        _render_paras(slide, cx, box["cy"] + max(0.0, (box["ch"] - needed) / 2.0),
                      cell_w - 16.0, paras)
        cells.append({"x": cx, "y": box["cy"], "w": cell_w, "h": box["ch"]})
    out = dict(box)
    out["cells"] = cells
    return out


# --------------------------------------------------------------------------- #
# Callouts and flow
# --------------------------------------------------------------------------- #


def takeaway(slide: Shape, x: float, y: float, w: float, h: float, text: str, *,
             label: str = "", tone: str = "primary", size: float = 14.0,
             text_color: Optional[str] = None, label_color: Optional[str] = None,
             pad: Any = "md") -> Dict[str, Any]:
    """Draw the dark conclusion callout: accent label plus white text.

    Args:
        slide: Slide to draw on.
        x, y, w, h: Callout box in px (full width or card width).
        text: One or two lines of conclusion text.
        label: Short accent label drawn above the text.
        tone: ``primary`` (navy, default) or ``accent`` (mint with teal label).
        size: Text size in px.
        text_color: Override the body text colour.
        label_color: Override the label colour.
        pad: Padding preset or explicit tuple.

    Returns:
        The callout box dict.
    """
    tone_key = _tone_of(tone, "primary")
    box = card(slide, x, y, w, h, tone=tone_key, pad=pad)
    dark = box["fill"] == "navy"
    body_color = text_color or ("white" if dark else "t1")
    lab_color = label_color or ("teal" if dark else "teal")
    cur = float(box["cy"])
    if label:
        _render_paras(slide, box["cx"], cur, float(box["cw"]),
                      [_para(truncate(str(label), 12, float(box["cw"]), True).upper(),
                             style_of("kicker", size=12, color=lab_color, spacing=2.0),
                             line_spacing=1.1)])
        cur += 18.0
    size_px = max(13.0, float(size))
    paras = [_para(str(text), style_of("card_body", size=size_px, color=body_color),
                   line_spacing=1.42)]
    room = float(box["cy"]) + float(box["ch"]) - cur
    while size_px > 13.0 and estimate_height(paras, float(box["cw"])) > room:
        size_px -= 0.5
        paras = [_para(str(text), style_of("card_body", size=size_px, color=body_color),
                       line_spacing=1.42)]
    needed = estimate_height(paras, float(box["cw"]))
    top = cur + max(0.0, (float(box["cy"]) + float(box["ch"]) - cur - needed) / 2.0) \
        if needed < (float(box["cy"]) + float(box["ch"]) - cur) - 4.0 else cur
    _render_paras(slide, box["cx"], top, float(box["cw"]), paras)
    return box


def bullets(slide: Shape, x: float, y: float, w: float, h: float,
            items: Iterable[Any], *, size: float = 13.0,
            color: Optional[str] = None, mark: str = "▪",
            gap: float = 7.0, line_spacing: float = 1.4,
            lead_color: Optional[str] = None, mark_color: Optional[str] = None,
            fit: bool = True) -> Dict[str, Any]:
    """Draw a bullet list, shrinking to fit rather than overflowing.

    Args:
        slide: Slide to draw on.
        x, y, w, h: Box in px.
        items: Strings or ``(lead, rest)`` pairs / ``{lead, text}`` dicts.
        size: Bullet size in px (never below 13).
        color: Text colour (palette key).
        mark: Bullet glyph; ``""`` keeps the hanging indent without a glyph.
        gap: Space after each bullet in px.
        line_spacing: Per-line multiplier.
        lead_color: Colour of the bold lead-in run.
        mark_color: Colour of the bullet glyph (defaults to teal; use ``white``
            on a navy card, where a teal glyph would disappear).
        fit: Shrink text when the list does not fit ``h``.

    Returns:
        A dict with the used box and the resolved ``size`` / ``lines`` count.
    """
    body_color = color or "t2"
    lead = lead_color or ("t1" if body_color in ("t2", "t1") else body_color)
    glyph_color = mark_color or {"white": "white", "pink": "brick"}.get(body_color, "teal")
    entries = [it for it in (items or []) if it not in (None, "")]
    if not entries:
        return {"x": x, "y": y, "w": w, "h": h, "size": size, "lines": 0}

    def build(size_px: float) -> List[Dict[str, Any]]:
        paras: List[Dict[str, Any]] = []
        for item in entries:
            if isinstance(item, dict):
                lead_text = str(item.get("lead", "") or "")
                rest = str(item.get("text", "") or "")
            elif isinstance(item, (tuple, list)) and len(item) == 2:
                lead_text, rest = str(item[0]), str(item[1])
            else:
                lead_text, rest = "", str(item)
            runs: List[Dict[str, Any]] = []
            if mark:
                runs.append({"text": mark + " ",
                             "style": style_of("card_body", size=size_px, color=glyph_color,
                                               bold=True)})
            if lead_text:
                runs.append({"text": lead_text,
                             "style": style_of("card_body", size=size_px, color=lead, bold=True)})
            runs.append({"text": rest, "style": style_of("card_body", size=size_px, color=body_color)})
            paras.append({"runs": runs, "align": None, "space_before": 0.0,
                          "space_after": gap, "line_spacing": line_spacing})
        return paras

    size_px = max(13.0, float(size))
    paras = build(size_px)
    while fit and size_px > 13.0 and estimate_height(paras, w) > float(h):
        size_px -= 0.5
        paras = build(size_px)
    _render_paras(slide, x, y, w, paras)
    return {"x": x, "y": y, "w": w, "h": h, "size": size_px, "lines": len(paras)}


def chip(slide: Shape, x: float, y: float, w: float, h: float, text: str, *,
         tone: str = "accent", size: float = 11.5,
         fill: Optional[str] = None, color: Optional[str] = None) -> Dict[str, Any]:
    """Draw a small rounded label chip (status, category, tag).

    Args:
        slide: Slide to draw on.
        x, y, w, h: Chip box in px.
        text: Chip text (truncated to one line).
        tone: ``accent`` (mint/teal), ``primary`` (navy/white), ``danger``
            (pink/brick), ``neutral`` or ``plain``.
        size: Text size in px (never below 11).
        fill: Explicit fill override.
        color: Explicit text colour override.

    Returns:
        The chip box dict.
    """
    tone_key = _tone_of(tone, "accent")
    fills = {"accent": ("mint", "teal"), "primary": ("navy", "white"),
             "danger": ("pink", "brick"), "alert": ("pink", "brick"),
             "neutral": ("light", "grayblue"), "tint": ("light", "grayblue"),
             "plain": ("light", "t2")}
    fill_key, ink = fills.get(tone_key, ("mint", "teal"))
    if fill is not None:
        fill_key = fill
    text_color = color or ink
    if color is None:
        # Match the pill to the surface it sits on: a teal label would sink into
        # the warning tint, and a navy label into the navy card.
        if fill_key == "pink":
            text_color = "brick"
        elif fill_key == "navy":
            text_color = "white"
    size_px = max(11.0, float(size))
    oval(slide, x, y, w, h, fill=fill_key)
    inner = max(10.0, w - 12.0)
    label = str(text)
    if _wrap_count(label, size_px, inner, True) > 1:
        label = label.replace(" ", "")            # never wrap a chip onto two lines
        label = truncate(label, size_px, inner, True)
    tb = _render_paras(slide, x + 6.0, y, inner,
                       [_para(label,
                              style_of("caption", size=size_px, color=text_color, bold=True),
                              align="center", line_spacing=1.05)],
                       anchor="middle")
    # A chip is one line by definition: let the renderer squeeze rather than wrap.
    try:
        tb.text_frame.word_wrap = False
        tb.text_frame.auto_size = None
    except (AttributeError, ValueError):  # pragma: no cover
        pass
    return {"x": x, "y": y, "w": w, "h": h, "fill": fill_key, "ink": text_color}


#: Private alias used by :func:`card_head`, whose ``chip`` argument shadows the name.
_chip = chip


def footnote(slide: Shape, x: float, y: float, w: float, text: str, *,
             size: float = 11.5, color: str = "t3", align: str = "left") -> Dict[str, Any]:
    """Draw a caption / source line (11.5px, never below 11px).

    Args:
        slide: Slide to draw on.
        x, y, w: Position and width in px; the height is measured.
        text: Caption text (wrapped to at most two lines).
        size: Size in px, clamped to the 11px lower bound.
        color: Palette key for the text.
        align: Paragraph alignment.

    Returns:
        The caption box dict.
    """
    size_px = max(11.0, float(size))
    body = str(text or "")
    if _wrap_count(body, size_px, w, False) > 2:
        lines: List[str] = []
        cur = ""
        for word in body.split(" "):
            trial = (cur + " " + word).strip()
            if measure_text(trial, size_px, False) > w * 2 and cur:
                lines.append(cur)
                cur = word
            else:
                cur = trial
        if cur:
            lines.append(cur)
        body = " ".join(lines[:2])
        body = truncate(body, size_px, w * 2 - size_px, False)
    paras = [_para(body, style_of("caption", size=size_px, color=color),
                   align=align, line_spacing=1.3)]
    h = estimate_height(paras, w)
    _render_paras(slide, x, y, w, paras)
    return {"x": x, "y": y, "w": w, "h": h, "size": size_px}


# --------------------------------------------------------------------------- #
# Process / comparison / matrix
# --------------------------------------------------------------------------- #


def process_steps(slide: Shape, x: float, y: float, w: float, h: float,
                  steps: Sequence[Any], *, node_h: Optional[float] = None,
                  gap: float = 24.0, tone: str = "plain",
                  arrow_color: str = "teal", size: float = 13.0) -> Dict[str, Any]:
    """Draw 2-3 process nodes joined by teal arrow connectors.

    Args:
        slide: Slide to draw on.
        x, y, w, h: Strip box in px.
        steps: ``[{label, text}]`` (strings are accepted too).
        node_h: Node height in px; defaults to the strip height.
        gap: Horizontal gap between a node and its arrow, in px.
        tone: Card tone for the nodes.
        arrow_color: Connector colour (palette key).
        size: Node text size in px.

    Returns:
        A dict with ``nodes`` and ``arrows`` boxes plus the strip box.
    """
    items = [s for s in (steps or []) if s not in (None, "", {})][:3]
    if not items:
        return {"x": x, "y": y, "w": w, "h": h, "nodes": [], "arrows": []}
    count = len(items)
    bw = float(w) - (count - 1) * float(gap)
    bw = max(80.0, bw / count)
    nh = float(node_h) if node_h else float(h)
    nh = min(nh, float(h))
    ny = float(y) + (float(h) - nh) / 2.0
    size_px = max(13.0, float(size))
    nodes: List[Dict[str, Any]] = []
    arrows: List[Dict[str, Any]] = []
    for i, item in enumerate(items):
        nx = float(x) + i * (bw + float(gap))
        if isinstance(item, dict):
            label = str(item.get("label", "") or "")
            text = str(item.get("text", "") or item.get("body", "") or "")
        else:
            label, text = "", str(item)
        head = truncate(label, size_px + 1, bw - 24.0, True) if label else ""
        paras: List[Dict[str, Any]] = []
        if head:
            paras.append(_para(head, style_of("card_title_sm", size=size_px + 1, color="navy"),
                               align="center", line_spacing=1.2, space_after=2.0))
        if text:
            body_size = max(11.5, size_px - 1.5)
            paras.append(_para(truncate(text, body_size, bw - 28.0, False),
                               style_of("card_body", size=body_size, color="t2"),
                               align="center", line_spacing=1.25))
        used = estimate_height(paras, bw - 24.0)
        box = card(slide, nx, ny, bw, nh, tone=tone,
                   pad=(max(6.0, (nh - used) / 2.0), 12.0, 6.0, 12.0))
        _render_paras(slide, box["cx"], box["cy"], float(box["cw"]), paras)
        nodes.append({"x": nx, "y": ny, "w": bw, "h": nh})
        if i < count - 1:
            ax1 = nx + bw + max(2.0, float(gap) * 0.15)
            ax2 = nx + bw + float(gap) - max(2.0, float(gap) * 0.15)
            mid = float(y) + float(h) / 2.0
            from .primitives import add_arrow as _arrow

            _arrow(slide, ax1, mid, ax2, mid, color=arrow_color, w=1.8)
            arrows.append({"x1": ax1, "y1": mid, "x2": ax2, "y2": mid})
    return {"x": x, "y": y, "w": w, "h": h, "nodes": nodes, "arrows": arrows}


def compare_pair(slide: Shape, x: float, y: float, w: float, h: float,
                 left: Dict[str, Any], right: Dict[str, Any], *,
                 vs: str = "VS", verdict: str = "", vs_w: float = 64.0,
                 tone_left: Optional[str] = None,
                 tone_right: Optional[str] = None) -> Dict[str, Any]:
    """Draw two contrast group cards with a ``VS`` marker between them.

    Args:
        slide: Slide to draw on.
        x, y, w, h: Comparison area in px.
        left: ``{title, body, items[], tone, chip, footer}`` for the left group.
        right: Same shape for the right group.
        vs: Marker text between the cards.
        verdict: One-line conclusion below the pair (optional).
        vs_w: Width of the marker gutter in px.
        tone_left: Tone override for the left card.
        tone_right: Tone override for the right card.

    Returns:
        A dict with ``left`` / ``right`` / ``vs`` / ``verdict`` boxes.
    """
    value = float(h)
    verdict_h = 0.0
    if verdict:
        verdict_h = min(60.0, max(34.0, value * 0.16))
    cards_h = max(80.0, value - verdict_h - (14.0 if verdict else 0.0))
    cw = (float(w) - float(vs_w)) / 2.0

    left_box = card(slide, x, y, cw, cards_h, tone=tone_left or left.get("tone") or "plain")
    card_head(slide, left_box, chip=str(left.get("chip", "") or ""),
              title=str(left.get("title", "") or ""), body=str(left.get("body", "") or ""),
              items=left.get("items"), footer=str(left.get("footer", "") or ""))
    right_box = card(slide, x + cw + float(vs_w), y, cw, cards_h,
                     tone=tone_right or right.get("tone") or "plain")
    card_head(slide, right_box, chip=str(right.get("chip", "") or ""),
              title=str(right.get("title", "") or ""), body=str(right.get("body", "") or ""),
              items=right.get("items"), footer=str(right.get("footer", "") or ""))

    mid_x = float(x) + cw + float(vs_w) / 2.0
    marker = 44.0
    oval(slide, mid_x - marker / 2.0, float(y) + cards_h / 2.0 - marker / 2.0, marker, marker,
         fill="navy")
    _render_paras(slide, mid_x - marker / 2.0, float(y) + cards_h / 2.0 - marker / 2.0,
                  marker,
                  [_para(truncate(str(vs), 13, marker - 6.0, True),
                         style_of("card_body", size=13, color="white", bold=True),
                         align="center", line_spacing=1.05)],
                  anchor="middle")
    result: Dict[str, Any] = {
        "x": x, "y": y, "w": w, "h": h,
        "left": left_box, "right": right_box,
        "vs": {"x": mid_x - marker / 2.0, "y": float(y) + cards_h / 2.0 - marker / 2.0,
               "w": marker, "h": marker},
    }
    if verdict:
        vbox = card(slide, x, float(y) + cards_h + 14.0, w, verdict_h, tone="accent",
                    pad=(8.0, 18.0, 8.0, 18.0))
        takeaway(slide, x, float(y) + cards_h + 14.0, w, verdict_h, str(verdict),
                 tone="accent", size=13.5, pad=(8.0, 18.0, 8.0, 18.0))
        result["verdict"] = vbox
    return result


def matrix_grid(slide: Shape, x: float, y: float, w: float, h: float,
                quadrants: Sequence[Any], *, gap: float = 20.0,
                center_label: str = "", center_dot: float = 20.0) -> Dict[str, Any]:
    """Draw a 2x2 mechanism matrix: four tone-tinted quadrants and a centre dot.

    Args:
        slide: Slide to draw on.
        x, y, w, h: Grid box in px (guide: 840 x 400 for 380x190 quadrants).
        quadrants: Four items ``[{no, title, condition, result, note, tone}]``
            in reading order left-top, right-top, left-bottom, right-bottom.
        gap: Gutter between quadrants in px.
        center_label: Text next to the centre anchor dot.
        center_dot: Centre dot diameter in px.

    Returns:
        A dict with ``cells`` (four boxes), ``center`` and the grid box.
    """
    items = [q for q in (quadrants or []) if isinstance(q, dict)]
    qw = (float(w) - float(gap)) / 2.0
    qh = (float(h) - float(gap)) / 2.0
    tone_fill = {"accent": "mint", "danger": "pink", "alert": "pink",
                 "neutral": "light", "tint": "light", "primary": "navy", "plain": "white"}
    cells: List[Dict[str, Any]] = []
    for i in range(4):
        col, row = i % 2, i // 2
        cx = float(x) + col * (qw + float(gap))
        cy = float(y) + row * (qh + float(gap))
        data = items[i] if i < len(items) else {}
        tone = str(data.get("tone") or ("accent" if i == 0 else
                                        "danger" if i == 1 else
                                        "neutral" if i == 2 else "tint")).lower()
        fill_key = tone_fill.get(tone, "light")
        stroke = {"mint": "teal", "pink": "brick", "light": "grayblue",
                  "navy": "navy", "white": "line"}.get(fill_key, "line")
        box = card(slide, cx, cy, qw, qh, tone=tone, fill=fill_key, line=stroke, line_w=2.0,
                   pad=(14.0, 16.0, 12.0, 16.0))
        ink = "white" if fill_key == "navy" else "t1"
        sub = "white" if fill_key == "navy" else "t2"
        cur = float(box["cy"])
        no = str(data.get("no", "") or "")
        title = str(data.get("title", "") or "")
        if no or title:
            runs: List[Dict[str, Any]] = []
            if no:
                # Same rule as the "条件 ·" lead-in: teal reads on tinted quadrants,
                # brick on the pink (danger) ones — teal on #FCE5E2 is only 2.74:1.
                no_color = ("white" if ink == "white"
                            else ("brick" if fill_key == "pink" else "teal"))
                runs.append({"text": no + "  ",
                             "style": style_of("card_title", size=17, color=no_color)})
            if title:
                runs.append({"text": truncate(title, 15, qw - 60.0, True),
                             "style": style_of("card_title", size=15, color=ink)})
            paras = [{"runs": runs, "align": None, "space_before": 0.0,
                      "space_after": 5.0, "line_spacing": 1.2}]
            _render_paras(slide, box["cx"], cur, float(box["cw"]), paras)
            cur += estimate_height(paras, float(box["cw"])) + 4.0
        for key, size, color, mark in (("condition", 13.0, sub, "条件 · "),
                                       ("result", 13.0, ink, "结果 · "),
                                       ("note", 11.5, sub, "")):
            text = str(data.get(key, "") or "")
            if not text:
                continue
            label = mark if key != "note" else ""
            runs = []
            if label and key == "condition":
                # The lead-in is teal on tinted quadrants; on the pink "danger"
                # quadrant brick keeps it readable (and inside the palette).
                lead = "white" if ink == "white" else ("brick" if fill_key == "pink" else "teal")
                runs.append({"text": label,
                             "style": style_of("card_body", size=size, color=lead, bold=True)})
            runs.append({"text": text,
                         "style": style_of("card_body" if key != "note" else "caption",
                                           size=size, color=color)})
            paras = [{"runs": runs, "align": None, "space_before": 0.0,
                      "space_after": 4.0, "line_spacing": 1.3}]
            room = float(box["cy"]) + float(box["ch"]) - cur
            if estimate_height(paras, float(box["cw"])) > room and size > 11.0:
                continue
            _render_paras(slide, box["cx"], cur, float(box["cw"]), paras)
            cur += estimate_height(paras, float(box["cw"]))
        cells.append(dict(box))

    cxx = float(x) + qw + float(gap) / 2.0
    cyy = float(y) + qh + float(gap) / 2.0
    oval(slide, cxx - float(center_dot) / 2.0, cyy - float(center_dot) / 2.0,
         float(center_dot), float(center_dot), fill="navy")
    if center_label:
        label = truncate(str(center_label), 11.5, qw * 0.6, False)
        wlabel = min(qw * 0.6, measure_text(label, 11.5, False) + 14.0)
        bx = cxx - wlabel / 2.0
        by = cyy + float(center_dot) / 2.0 + 3.0
        rect(slide, bx, by, wlabel, 17.0, fill="white", line="line", line_w=1.0)
        _render_paras(slide, bx, by, wlabel,
                      [_para(label, style_of("caption", size=11.5, color="navy", bold=True),
                             align="center", line_spacing=1.05)], anchor="middle")
    else:
        by = cyy
    return {"x": x, "y": y, "w": w, "h": h, "cells": cells,
            "center": {"x": cxx, "y": cyy, "d": float(center_dot), "label_y": by}}


# --------------------------------------------------------------------------- #
# Tables
# --------------------------------------------------------------------------- #


def table(slide: Shape, x: float, y: float, w: float,
          columns: Sequence[Any], rows: Sequence[Sequence[Any]], *,
          col_widths: Optional[Sequence[float]] = None, row_h: float = 46.0,
          head_h: float = 42.0, highlight_col: int = -1,
          highlight_cell: Optional[Tuple[int, int]] = None,
          first_col_bold: bool = True, mark_highlight: bool = False,
          unit: str = "") -> Dict[str, Any]:
    """Draw a data table: navy header, zebra rows, 1px grid, optional highlight.

    Args:
        slide: Slide to draw on.
        x, y, w: Table position and width in px (guide: 40 -> 1240).
        columns: Header labels.
        rows: Row cell values (strings; numbers are stringified).
        col_widths: Explicit column widths in px (normalised to ``w``).
        row_h: Body row height in px (guide: 44-52).
        head_h: Header row height in px.
        highlight_col: 0-based column index to tint with mint (``-1`` = none).
        highlight_cell: ``(row, col)`` cell to tint (``row`` counts body rows).
        first_col_bold: Draw the first column in bold navy.
        mark_highlight: Prefix the highlighted cell with a check mark.
        unit: Optional unit note appended to the header row.

    Returns:
        A dict with the table box, ``bottom`` (px), ``row_h`` and ``col_x``
        (column left edges) so callers can place captions or overlays.
    """
    heads = [str(c) for c in (columns or [])]
    body = [list(r) for r in (rows or [])]
    if not heads:
        raise ValueError("table() needs at least one column")
    ncols = len(heads)
    if col_widths and len(col_widths) == ncols:
        total = float(sum(col_widths)) or float(w)
        widths = [float(cw) / total * float(w) for cw in col_widths]
    else:
        widths = [float(w) / ncols] * ncols
    col_x: List[float] = []
    acc = float(x)
    for cw in widths:
        col_x.append(acc)
        acc += cw

    nrows = len(body)
    head_h = max(30.0, float(head_h))
    row_h = float(row_h) if float(row_h) > 0 else 46.0
    rect(slide, float(x) - 0.5, float(y) - 0.5, float(w) + 1.0, head_h + 1.0, fill="navy")
    for i, head in enumerate(heads):
        pad = 12.0
        text = head if not unit or i < ncols - 1 else f"{head} ({unit})"
        _render_paras(slide, col_x[i] + pad, float(y), max(10.0, widths[i] - 2 * pad),
                      [_para(truncate(text, 13, max(10.0, widths[i] - 2 * pad), True),
                             style_of("table_head", color="white"),
                             align="left", line_spacing=1.05)], anchor="middle")

    for r, cells in enumerate(body):
        ry = float(y) + head_h + r * row_h
        if r % 2 == 1:
            rect(slide, float(x) - 0.5, ry, float(w) + 1.0, row_h + 1.0, fill="light")
        for c in range(ncols):
            cx, cw = col_x[c], widths[c]
            value = str(cells[c]) if c < len(cells) and cells[c] is not None else ""
            is_hl = (c == highlight_col) or (highlight_cell == (r, c))
            if is_hl:
                rect(slide, cx - 0.5, ry, cw + 1.0, row_h + 1.0, fill="mint")
            if c == 0 and first_col_bold and not is_hl:
                color = "navy"
                bold = True
            else:
                color = "t1" if is_hl else ("t1" if c == 0 else "t2")
                bold = False
            if is_hl and mark_highlight and value:
                value = "✓ " + value
            pad = 12.0
            size = 12.5
            while size > 11.0 and _wrap_count(value, size, max(10.0, cw - 2 * pad), bold) > 2:
                size -= 0.5
            _render_paras(slide, cx + pad, ry, max(10.0, cw - 2 * pad),
                          [_para(value, style_of("table_cell", size=size, color=color, bold=bold),
                                 align="left", line_spacing=1.22)], anchor="middle")

    bottom = float(y) + head_h + nrows * row_h
    # 1px rules on every row boundary.
    for r in range(nrows + 1):
        ly = float(y) + head_h + r * row_h
        rect(slide, float(x), ly, float(w), 1, fill="line")
    for c in range(ncols + 1):
        lx = float(x) + sum(widths[:c])
        if c == ncols:
            lx = float(x) + float(w) - 1.0
        # One continuous rule per column, so row boundaries never leave a seam.
        rect(slide, lx, float(y), 1, bottom - float(y), fill="line")
    rect(slide, float(x), float(y), float(w), 1, fill="navy")

    return {"x": float(x), "y": float(y), "w": float(w), "h": bottom - float(y),
            "bottom": bottom, "head_h": head_h, "row_h": row_h,
            "rows": nrows, "cols": ncols, "col_x": col_x, "col_w": widths}
