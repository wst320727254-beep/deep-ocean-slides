# -*- coding: utf-8 -*-
"""Low-level python-pptx primitives expressed in **design pixels**.

Everything here speaks the 1280x720 px language of the style guide; the
conversion to EMU happens at the boundary.  Layout code should use these
helpers instead of touching python-pptx directly, so that the deck stays
inside the safe margins and the linter can reason about it.

Frozen API (other modules depend on these signatures)
-----------------------------------------------------
``rgb(key)``                        palette key / role / ``#hex`` -> RGBColor
``rect(slide, x, y, w, h, ...)``    rectangle or rounded rectangle, px units
``oval(slide, x, y, w, h, ...)``    ellipse, px units
``add_arrow(slide, x1, y1, x2, y2, color, ...)``
``add_text(slide, x, y, w, h, paras, ...)``
``P(...)`` / ``T(...)``             paragraph / run builders
``bullets(slide, x, y, w, h, items, ...)``
``measure_text(text, size_px, bold)``
``wrap_lines(text, size_px, width_px, bold)``
``text_height(text, size_px, width_px, bold, line_height)``
``fit_size(text, size_px, width_px, max_lines, line_height)``
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple, Union

from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_CONNECTOR, MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.oxml.ns import qn
from pptx.util import Emu, Pt

from . import color as _color
from . import spec as _spec
from . import tokens
from .units import px_to_emu, px_to_pt

Shape = Any
ColorLike = Union[str, RGBColor]

#: Deck-wide font override, set by :mod:`deepocean.build` from ``meta.fonts``.
_FONT_OVERRIDE: Dict[str, Optional[str]] = {"latin": None, "cjk": None}


def set_fonts(latin: Optional[str] = None, cjk: Optional[str] = None) -> Dict[str, Optional[str]]:
    """Force the Latin / CJK typeface used by every run (None restores default)."""
    _FONT_OVERRIDE["latin"] = latin
    _FONT_OVERRIDE["cjk"] = cjk
    return dict(_FONT_OVERRIDE)


def default_fonts() -> Tuple[str, str]:
    return (
        _FONT_OVERRIDE["latin"] or tokens.FONTS["ppt_latin"],
        _FONT_OVERRIDE["cjk"] or tokens.FONTS["ppt_cjk"],
    )


# --------------------------------------------------------------------------- #
# Build context
# --------------------------------------------------------------------------- #


@dataclass
class Ctx:
    """Everything a layout function needs besides the slide itself."""

    deck: "_spec.Deck"
    index: int                     # 1-based page number
    total: int
    page: "_spec.Page"
    hero: bool = False

    def get(self, key: str, default: Any = None) -> Any:
        return self.page.get(key, default)

    def note(self) -> str:
        return self.deck.resolved_footer_note()


# --------------------------------------------------------------------------- #
# Colour & style resolution
# --------------------------------------------------------------------------- #


def rgb(value: ColorLike) -> RGBColor:
    """Resolve a palette key, role name or ``#RRGGBB`` to a pptx colour."""
    if isinstance(value, RGBColor):
        return value
    hexv = tokens.hex_of(str(value))
    r, g, b = _color.hex_to_rgb(hexv)
    return RGBColor(r, g, b)


def hexof(value: ColorLike) -> str:
    if isinstance(value, RGBColor):
        return _color.rgb_to_hex((value[0], value[1], value[2]))
    return tokens.hex_of(str(value))


_ALIGN = {
    "left": PP_ALIGN.LEFT,
    "center": PP_ALIGN.CENTER,
    "centre": PP_ALIGN.CENTER,
    "right": PP_ALIGN.RIGHT,
    "justify": PP_ALIGN.JUSTIFY,
}

_ANCHOR = {
    "top": MSO_ANCHOR.TOP,
    "middle": MSO_ANCHOR.MIDDLE,
    "center": MSO_ANCHOR.MIDDLE,
    "bottom": MSO_ANCHOR.BOTTOM,
}


def style(token: Union[str, tokens.TypeToken] = "card_body", **overrides: Any) -> Dict[str, Any]:
    """Build a run style from a type token, with px-based overrides.

    Overrides: ``size`` (px), ``bold``, ``italic``, ``color``, ``spacing`` (px),
    ``font_latin``, ``font_cjk``.
    """
    if isinstance(token, str):
        base = tokens.type_token(token)
        out: Dict[str, Any] = {
            "size": base.px,
            "bold": base.bold,
            "color": base.color,
            "spacing": base.letter_spacing,
            "line_height": base.line_height,
        }
    else:
        out = {
            "size": token.px,
            "bold": token.bold,
            "color": token.color,
            "spacing": token.letter_spacing,
            "line_height": token.line_height,
        }
    for key, value in overrides.items():
        if value is not None:
            out[key] = value
    return out


def T(text: str, token: Union[str, tokens.TypeToken] = "card_body", **overrides: Any) -> Dict[str, Any]:
    """A run: ``T("+328%", "kpi_value", color="teal")``."""
    return {"text": text, "style": style(token, **overrides)}


def P(runs: Union[str, Dict[str, Any], Sequence[Dict[str, Any]]],
      align: Optional[str] = None,
      space_before: Optional[float] = None,
      space_after: Optional[float] = None,
      line_spacing: Optional[float] = None,
      bullet: bool = False) -> Dict[str, Any]:
    """A paragraph spec consuming :func:`T` runs.

    ``align`` / spacing values are px (spacing converted to pt internally).
    """
    if isinstance(runs, str):
        runs = [T(runs)]
    elif isinstance(runs, dict):
        runs = [runs]
    return {
        "runs": list(runs),
        "align": align,
        "space_before": space_before,
        "space_after": space_after,
        "line_spacing": line_spacing,
        "bullet": bullet,
    }


# --------------------------------------------------------------------------- #
# Shapes
# --------------------------------------------------------------------------- #


def no_shadow(shape: Shape) -> Shape:
    try:
        shape.shadow.inherit = False
    except (AttributeError, ValueError):  # pragma: no cover - group shapes etc.
        pass
    return shape


def set_opacity(shape: Shape, percent: float) -> Shape:
    """Apply transparency (0-100, where 100 = opaque) to a solid fill."""
    try:
        fill = shape.fill.fore_color._xFill
    except AttributeError:  # pragma: no cover
        return shape
    srgb = fill.find(qn("a:srgbClr"))
    if srgb is None:
        return shape
    alpha = srgb.find(qn("a:alpha"))
    if alpha is None:
        alpha = srgb.makeelement(qn("a:alpha"), {})
        srgb.append(alpha)
    alpha.set("val", str(int(max(0.0, min(100.0, percent)) * 1000)))
    return shape


def _apply_fill(shape: Shape, fill: Optional[ColorLike], opacity: Optional[float]) -> Shape:
    if fill is None:
        shape.fill.background()
    else:
        shape.fill.solid()
        shape.fill.fore_color.rgb = rgb(fill)
        if opacity is not None and opacity < 100:
            set_opacity(shape, opacity)
    return shape


def _apply_line(shape: Shape, line: Optional[ColorLike], width_px: float) -> Shape:
    if line is None:
        shape.line.fill.background()
    else:
        shape.line.color.rgb = rgb(line)
        shape.line.width = Pt(px_to_pt(width_px))
    return shape


def rect(slide: Shape, x: float, y: float, w: float, h: float,
         fill: Optional[ColorLike] = None,
         line: Optional[ColorLike] = None,
         line_w: float = 1.0,
         radius: Optional[float] = None,
         opacity: Optional[float] = None,
         shape: Optional[MSO_SHAPE] = None) -> Shape:
    """Rectangle (or rounded rectangle when ``radius`` px is given)."""
    kind = shape or (MSO_SHAPE.ROUNDED_RECTANGLE if radius else MSO_SHAPE.RECTANGLE)
    sp = slide.shapes.add_shape(kind, Emu(px_to_emu(x)), Emu(px_to_emu(y)),
                                Emu(px_to_emu(w)), Emu(px_to_emu(h)))
    no_shadow(sp)
    _apply_fill(sp, fill, opacity)
    _apply_line(sp, line, line_w)
    if radius and kind in (MSO_SHAPE.ROUNDED_RECTANGLE, MSO_SHAPE.ROUND_2_SAME_RECTANGLE):
        try:
            sp.adjustments[0] = max(0.0, min(0.5, radius / max(1.0, min(w, h))))
        except (IndexError, ValueError):  # pragma: no cover
            pass
    return sp


def oval(slide: Shape, x: float, y: float, w: float, h: float,
         fill: Optional[ColorLike] = None,
         line: Optional[ColorLike] = None,
         line_w: float = 1.0,
         opacity: Optional[float] = None) -> Shape:
    return rect(slide, x, y, w, h, fill=fill, line=line, line_w=line_w,
                opacity=opacity, shape=MSO_SHAPE.OVAL)


def shape_with_text(slide: Shape, x: float, y: float, w: float, h: float,
                    text: str, token: str = "node", **kw: Any) -> Shape:
    """A filled shape with centred text (chips, flow nodes, tags)."""
    sp = rect(slide, x, y, w, h, **kw)
    tf = sp.text_frame
    tf.word_wrap = True
    tf.margin_left = Emu(0)
    tf.margin_right = Emu(0)
    tf.margin_top = Emu(0)
    tf.margin_bottom = Emu(0)
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    para = tf.paragraphs[0]
    para.alignment = PP_ALIGN.CENTER
    st = style(token)
    run = para.add_run()
    _write_run(run, text, st)
    return sp


def add_arrow(slide: Shape, x1: float, y1: float, x2: float, y2: float,
              color: ColorLike = "accent", w: float = 1.6,
              dash: Optional[str] = None, head: bool = True) -> Shape:
    """Straight connector with an optional triangle head."""
    conn = slide.shapes.add_connector(
        MSO_CONNECTOR.STRAIGHT,
        Emu(px_to_emu(x1)), Emu(px_to_emu(y1)),
        Emu(px_to_emu(x2)), Emu(px_to_emu(y2)))
    no_shadow(conn)
    conn.line.color.rgb = rgb(color)
    conn.line.width = Pt(w)
    ln = conn.line._get_or_add_ln()
    if dash:
        ln.append(ln.makeelement(qn("a:prstDash"), {"val": dash}))
    if head:
        ln.append(ln.makeelement(qn("a:tailEnd"), {"type": "triangle", "w": "med", "len": "med"}))
    return conn


def hairline(slide: Shape, x: float, y: float, w: float, color: ColorLike = "line",
             thickness: float = 1.0) -> Shape:
    """A 1px divider drawn as a thin filled rectangle (prints crisply)."""
    return rect(slide, x, y, w, thickness, fill=color)


def _asset_roots(base_dir: Optional[str]) -> List[str]:
    """Directories a relative image path may be resolved against, in order.

    The deck's own folder wins (so a deck folder stays portable), then the
    working directory, then the checkout's ``examples/`` — the last one is what
    makes the bundled demo work from anywhere, since its figure lives in the
    repository next to ``examples/demo-deck.yaml``.
    """
    roots: List[str] = []
    if base_dir:
        roots.append(base_dir)
    roots.append(os.getcwd())
    here = os.path.dirname(os.path.abspath(__file__))            # .../src/deepocean
    package_root = os.path.dirname(os.path.dirname(here))        # repo root (source checkout)
    roots.append(package_root)
    roots.append(os.path.join(package_root, "examples"))
    return roots


def resolve_asset(path: str, base_dir: Optional[str] = None) -> str:
    """Find an image referenced by a deck."""
    if not path:
        raise FileNotFoundError("empty image path")
    candidate = os.path.expanduser(str(path))
    search: List[str] = []
    if os.path.isabs(candidate):
        search.append(candidate)
    else:
        search += [os.path.join(root, candidate) for root in _asset_roots(base_dir)]
    for item in search:
        if os.path.exists(item):
            return item
    raise FileNotFoundError(f"image not found: {path} (looked in {', '.join(search[:4])})")


def image_size(path: str) -> Tuple[int, int]:
    """(width, height) in px, without decoding the whole file twice."""
    from PIL import Image

    with Image.open(path) as img:
        return img.size


def fit_box(path: str, x: float, y: float, w: float, h: float,
            *, mode: str = "contain", align: str = "center",
            valign: str = "middle") -> Tuple[float, float, float, float]:
    """Place an image of natural size ``path`` inside ``x, y, w, h`` (px).

    ``contain`` keeps the aspect ratio and centres the image; ``cover`` fills the
    box and is intended for figures that may be cropped.  Returns the px rect the
    picture should occupy so callers can draw a frame around exactly that.
    """
    try:
        iw, ih = image_size(path)
    except Exception:
        iw, ih = int(w), int(h)
    if iw <= 0 or ih <= 0:
        iw, ih = int(w), int(h)
    scale = min(w / iw, h / ih) if mode == "contain" else max(w / iw, h / ih)
    fw, fh = iw * scale, ih * scale
    if align == "left":
        fx = x
    elif align == "right":
        fx = x + w - fw
    else:
        fx = x + (w - fw) / 2.0
    if valign == "top":
        fy = y
    elif valign == "bottom":
        fy = y + h - fh
    else:
        fy = y + (h - fh) / 2.0
    return (fx, fy, fw, fh)


def picture(slide: Shape, path: str, x: float, y: float, w: float, h: float,
            *, mode: str = "contain", align: str = "center", valign: str = "middle",
            base_dir: Optional[str] = None) -> Tuple[Shape, Tuple[float, float, float, float]]:
    """Insert an image with ``contain`` fit; returns (shape, fitted px rect)."""
    resolved = resolve_asset(path, base_dir)
    rect_px = fit_box(resolved, x, y, w, h, mode=mode, align=align, valign=valign)
    pic = slide.shapes.add_picture(
        resolved, Emu(px_to_emu(rect_px[0])), Emu(px_to_emu(rect_px[1])),
        Emu(px_to_emu(rect_px[2])), Emu(px_to_emu(rect_px[3])))
    no_shadow(pic)
    return pic, rect_px


# --------------------------------------------------------------------------- #
# Text
# --------------------------------------------------------------------------- #


def _write_run(run: Shape, text: str, st: Dict[str, Any]) -> None:
    run.text = text
    font = run.font
    font.size = Pt(px_to_pt(st.get("size", 14)))
    font.bold = bool(st.get("bold", False))
    font.italic = bool(st.get("italic", False))
    font.underline = bool(st.get("underline", False))
    if st.get("color") is not None:
        font.color.rgb = rgb(st["color"])
    latin = st.get("font_latin") or _FONT_OVERRIDE["latin"] or tokens.FONTS["ppt_latin"]
    cjk = st.get("font_cjk") or _FONT_OVERRIDE["cjk"] or tokens.FONTS["ppt_cjk"]
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


def text_box(slide: Shape, x: float, y: float, w: float, h: float,
             anchor: str = "top", wrap: bool = True) -> Tuple[Shape, Shape]:
    tb = slide.shapes.add_textbox(Emu(px_to_emu(x)), Emu(px_to_emu(y)),
                                  Emu(px_to_emu(w)), Emu(px_to_emu(h)))
    tf = tb.text_frame
    tf.word_wrap = wrap
    tf.margin_left = Emu(0)
    tf.margin_right = Emu(0)
    tf.margin_top = Emu(0)
    tf.margin_bottom = Emu(0)
    tf.vertical_anchor = _ANCHOR.get(anchor, MSO_ANCHOR.TOP)
    return tb, tf


def add_text(slide: Shape, x: float, y: float, w: float, h: float,
             paras: Union[str, Dict[str, Any], Sequence[Dict[str, Any]]],
             anchor: str = "top", wrap: bool = True) -> Shape:
    """Write paragraphs into a fresh text box (px coordinates)."""
    if isinstance(paras, (str, dict)):
        paras = [paras]
    tb, tf = text_box(slide, x, y, w, h, anchor=anchor, wrap=wrap)
    first = True
    for spec_ in paras:
        if isinstance(spec_, str):
            spec_ = P(spec_)
        para = tf.paragraphs[0] if first else tf.add_paragraph()
        first = False
        align = spec_.get("align")
        if align:
            para.alignment = _ALIGN.get(align, PP_ALIGN.LEFT)
        if spec_.get("space_before") is not None:
            para.space_before = Pt(spec_["space_before"])
        if spec_.get("space_after") is not None:
            para.space_after = Pt(spec_["space_after"])
        if spec_.get("line_spacing") is not None:
            para.line_spacing = float(spec_["line_spacing"])
        for run_spec in spec_.get("runs", []):
            run = para.add_run()
            _write_run(run, str(run_spec.get("text", "")), run_spec.get("style", {}))
    return tb


def bullets(slide: Shape, x: float, y: float, w: float, h: float,
            items: Iterable[Any], token: str = "card_body",
            color: Optional[ColorLike] = None, mark: str = "▪",
            gap_px: float = 6.0, line_spacing: Optional[float] = None,
            size_px: Optional[float] = None, bold_lead: bool = False) -> Shape:
    """A bullet list; strings or ``(lead, rest)`` pairs.

    ``mark`` may be ``""`` to drop the glyph (the mark column is kept so
    wrapped lines stay aligned).
    """
    paras: List[Dict[str, Any]] = []
    st = style(token)
    if size_px:
        st["size"] = size_px
    if color:
        st["color"] = color
    for item in items:
        if isinstance(item, dict):
            lead = str(item.get("lead", ""))
            rest = str(item.get("text", ""))
        elif isinstance(item, (tuple, list)) and len(item) == 2:
            lead, rest = str(item[0]), str(item[1])
        else:
            lead, rest = "", str(item)
        runs: List[Dict[str, Any]] = []
        if mark:
            runs.append({"text": f"{mark} ", "style": dict(st, color=color or "accent", bold=True)})
        if lead:
            runs.append({"text": lead, "style": dict(st, bold=True, color=color or "t1")})
        runs.append({"text": rest, "style": dict(st)})
        paras.append(P(runs, line_spacing=line_spacing or st.get("line_height", 1.55),
                       space_after=gap_px))
    return add_text(slide, x, y, w, h, paras)


# --------------------------------------------------------------------------- #
# Text metrics (CJK aware, good enough to catch overflow)
# --------------------------------------------------------------------------- #

_NARROW = set("ilI.,:;!|'()[]{}/\\ ")
_WIDE = set("mwMW@%&")


def measure_text(text: str, size_px: float, bold: bool = False) -> float:
    """Estimated rendered width in px on the 1280x720 canvas."""
    factor = 1.06 if bold else 1.0
    total = 0.0
    for ch in text:
        code = ord(ch)
        if code > 0x2E7F:                     # CJK / full-width
            total += size_px * factor
        elif ch in _NARROW:
            total += size_px * 0.30 * factor
        elif ch in _WIDE:
            total += size_px * 0.95 * factor
        else:
            total += size_px * 0.55 * factor
    return total


def wrap_lines(text: str, size_px: float, width_px: float, bold: bool = False) -> List[str]:
    """Greedy line breaking: CJK breaks per character, Latin per word.

    A single word wider than the box is hard-broken, which mirrors what
    PowerPoint does and keeps overflow estimates honest.
    """
    if not text:
        return [""]
    lines: List[str] = []
    current = ""
    word = ""

    def push() -> None:
        nonlocal current
        lines.append(current)
        current = ""

    def append(unit: str) -> None:
        nonlocal current
        if not unit:
            return
        if not current and measure_text(unit, size_px, bold) > width_px:
            for ch in unit:                      # hard break an over-long word
                if current and measure_text(current + ch, size_px, bold) > width_px:
                    push()
                current += ch
            return
        if current and measure_text(current + unit, size_px, bold) > width_px:
            push()
        current += unit

    for ch in text:
        if ch == "\n":
            if word:
                append(word)
                word = ""
            push()
            continue
        if ord(ch) > 0x2E7F or ch in _NARROW or ch in _WIDE:
            if word:
                append(word)
                word = ""
            append(ch)
        else:
            word += ch
    if word:
        append(word)
    if current or not lines:
        lines.append(current)
    return lines


def line_count(text: str, size_px: float, width_px: float, bold: bool = False) -> int:
    return len(wrap_lines(text, size_px, width_px, bold))


def text_height(text: str, size_px: float, width_px: float,
                bold: bool = False, line_height: float = 1.5) -> float:
    """Estimated rendered height in px."""
    return line_count(text, size_px, width_px, bold) * size_px * line_height


def fit_size(text: str, size_px: float, width_px: float, max_lines: int,
             line_height: float = 1.5, min_px: float = 11.0) -> float:
    """Largest size <= ``size_px`` that fits ``text`` into ``max_lines``."""
    size = size_px
    while size > min_px and line_count(text, size, width_px, False) > max_lines:
        size -= 0.5
    return round(size, 1)


def truncate(text: str, size_px: float, width_px: float,
             bold: bool = False, ellipsis: str = "…") -> str:
    """Clip a string to one line, adding an ellipsis when needed."""
    if measure_text(text, size_px, bold) <= width_px:
        return text
    out = ""
    for ch in text:
        if measure_text(out + ch + ellipsis, size_px, bold) > width_px:
            break
        out += ch
    return out + ellipsis
