# -*- coding: utf-8 -*-
"""Deck document -> PowerPoint compiler.

The compiler stays deliberately thin: it owns the canvas, the file-level theme
(colours + fonts so PowerPoint's own pickers match the design), core document
properties and the page/chrome loop.  All visual decisions live in
:mod:`deepocean.layouts`.
"""

from __future__ import annotations

import os
import shutil
import zipfile
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from pptx import Presentation
from pptx.oxml.ns import qn
from pptx.util import Emu

from . import layouts, primitives, schema, spec as spec_mod, tokens
from .units import px_to_emu

THEME_PART = "ppt/theme/theme1.xml"

#: Theme slot -> palette key.  PowerPoint shows these in its colour picker.
THEME_COLOURS = {
    "dk1": "t1",
    "lt1": "white",
    "dk2": "navy",
    "lt2": "light",
    "accent1": "navy",
    "accent2": "teal",
    "accent3": "grayblue",
    "accent4": "brick",
    "accent5": "mint",
    "accent6": "line",
    "hlink": "teal",
    "folHlink": "grayblue",
}

A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"


@dataclass
class BuildResult:
    """Everything a caller needs to know about one compilation."""

    path: str
    pages: int
    problems: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.problems


# --------------------------------------------------------------------------- #
# Canvas
# --------------------------------------------------------------------------- #


def new_presentation() -> Presentation:
    """A blank 1280x720 px (13.333x7.5 in) presentation."""
    prs = Presentation()
    prs.slide_width = Emu(px_to_emu(tokens.CANVAS["width_px"]))
    prs.slide_height = Emu(px_to_emu(tokens.CANVAS["height_px"]))
    return prs


def _blank_layout(prs: Presentation):
    for layout in prs.slide_layouts:
        if layout.name.lower().strip() == "blank":
            return layout
    return prs.slide_layouts[6]


SLIDE_NAME_PREFIX = "deepocean"


def annotate_slide(slide: Any, page: "spec_mod.Page", ctx: primitives.Ctx) -> None:
    """Record ``deepocean:<layout>:<hero>`` as the slide name.

    Office keeps the ``cSld/@name`` attribute, so a deck can be traced back to
    the spec (and re-checked) even when only the .pptx survives.
    """
    try:
        csld = slide._element.find(qn("p:cSld"))
        if csld is not None:
            csld.set("name", f"{SLIDE_NAME_PREFIX}:{page.layout}:{'1' if ctx.hero else '0'}")
            return
    except (AttributeError, ValueError):  # pragma: no cover - exotic templates
        pass
    try:  # fall back to the first shape name, harmless for PowerPoint
        slide.shapes[0].name = f"{SLIDE_NAME_PREFIX}:{page.layout}"
    except (IndexError, AttributeError):  # pragma: no cover
        pass


def layout_names_of(prs: Presentation) -> list:
    """Best-effort recovery of the layout of every slide, in order."""
    out = []
    for slide in prs.slides:
        try:
            csld = slide._element.find(qn("p:cSld"))
            name = csld.get("name") if csld is not None else ""
        except AttributeError:  # pragma: no cover
            name = ""
        parts = (name or "").split(":")
        out.append(parts[1] if len(parts) >= 2 and parts[0] == SLIDE_NAME_PREFIX else "")
    return out


# --------------------------------------------------------------------------- #
# Build
# --------------------------------------------------------------------------- #


def build(deck: spec_mod.Deck, out_path: Optional[str] = None,
          *, check: bool = True, patch_theme: bool = True,
          strict: bool = False) -> BuildResult:
    """Compile ``deck`` to a .pptx file and return a :class:`BuildResult`.

    ``check=True`` runs the structural validation from :mod:`deepocean.spec`
    plus the layout field table; the resulting problems are reported but do not
    abort unless ``strict=True``.
    """
    problems = spec_mod.validate(deck, schema.field_table())
    if problems and strict:
        raise spec_mod.SpecError("deck is invalid:\n  - " + "\n  - ".join(problems))

    fonts = _fonts_of(deck)
    primitives.set_fonts(*fonts)

    prs = new_presentation()
    _set_core_properties(prs, deck)
    layout = _blank_layout(prs)
    total = len(deck.pages)

    for index, page in enumerate(deck.pages, 1):
        if page.layout in schema.ALIASES:
            page.layout = schema.resolve(page.layout)
        slide = prs.slides.add_slide(layout)
        ctx = primitives.Ctx(deck=deck, index=index, total=total, page=page,
                             hero=schema.is_hero(page.layout))
        annotate_slide(slide, page, ctx)
        layouts.build_page(slide, page, ctx)

    if not out_path:
        base = os.path.splitext(os.path.basename(deck.source_path or "deck"))[0]
        out_path = base + ".pptx"
    out_path = os.path.abspath(out_path)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    prs.save(out_path)

    if patch_theme:
        patch_theme_xml(out_path, fonts)

    warnings: List[str] = []
    if check:
        warnings = [p for p in spec_mod.validate(deck, schema.field_table())
                    if p not in problems]
    return BuildResult(path=out_path, pages=total, problems=problems, warnings=warnings)


def build_file(path: str, out_path: Optional[str] = None, **kw: Any) -> BuildResult:
    return build(spec_mod.Deck.load(path), out_path, **kw)


def _fonts_of(deck: spec_mod.Deck) -> tuple:
    """Resolve the Latin/CJK pairing, honouring ``meta.fonts`` when present."""
    meta = getattr(deck, "meta", None)
    requested: Dict[str, Any] = {}
    if meta is not None:
        requested = getattr(meta, "fonts", None) or {}
    latin = requested.get("latin") if isinstance(requested, dict) else None
    cjk = requested.get("cjk") if isinstance(requested, dict) else None
    return (primitives.default_fonts()[0] if not latin else str(latin),
            primitives.default_fonts()[1] if not cjk else str(cjk))


def _set_core_properties(prs: Presentation, deck: spec_mod.Deck) -> None:
    meta = deck.meta
    cp = prs.core_properties
    cp.title = meta.title
    cp.subject = meta.subtitle or meta.kicker
    cp.author = ", ".join(meta.authors) if meta.authors else "Deep Ocean Slides"
    cp.last_modified_by = "Deep Ocean Slides"
    cp.category = "Academic presentation"
    cp.keywords = f"{tokens.NAME}; academic slides; {meta.journal}".strip("; ")
    cp.comments = (f"Generated by Deep Ocean Slides v{tokens.VERSION}. "
                   f"Design system: {tokens.HOMEPAGE}")
    cp.revision = 1


# --------------------------------------------------------------------------- #
# File-level theme so PowerPoint's own colour picker matches the design
# --------------------------------------------------------------------------- #


def patch_theme_xml(path: str, fonts: Optional[tuple] = None) -> bool:
    """Rewrite ``ppt/theme/theme1.xml`` with the Deep Ocean colour + font scheme.

    Office stores theme colours in the package rather than the API, so we patch
    the saved file.  The existing XML skeleton is preserved (Office is picky
    about ``fmtScheme``), only the colour values and typefaces are swapped.
    Returns True when the theme was rewritten.
    """
    if not os.path.exists(path):
        raise FileNotFoundError(path)
    try:
        from lxml import etree
    except ImportError:  # pragma: no cover - lxml ships with python-pptx
        return False

    latin, cjk = fonts or primitives.default_fonts()

    with zipfile.ZipFile(path, "r") as zin:
        items = [(info, zin.read(info.filename)) for info in zin.infolist()]

    changed = False
    rebuilt: List[tuple] = []
    for info, data in items:
        if info.filename == THEME_PART:
            new_data = _restyle_theme(data, etree, latin, cjk)
            changed = new_data != data
            data = new_data
        rebuilt.append((info, data))
    if not changed:
        return False

    tmp = path + ".themetmp"
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zout:
        for info, data in rebuilt:
            zout.writestr(info, data)
    shutil.move(tmp, path)
    return True


def _restyle_theme(data: bytes, etree: Any, latin: str, cjk: str) -> bytes:
    try:
        root = etree.fromstring(data)
    except etree.XMLSyntaxError:  # pragma: no cover
        return data
    ns = {"a": A_NS}

    scheme = root.find(".//a:clrScheme", ns)
    if scheme is not None:
        for slot, key in THEME_COLOURS.items():
            node = scheme.find(f"a:{slot}", ns)
            if node is None:
                continue
            hexv = tokens.hex_of(key).lstrip("#")
            for child in list(node):
                node.remove(child)
            srgb = etree.SubElement(node, f"{{{A_NS}}}srgbClr")
            srgb.set("val", hexv)

    for tag in ("a:majorFont", "a:minorFont"):
        font = root.find(f".//{tag}", ns)
        if font is None:
            continue
        latin_node = font.find("a:latin", ns)
        if latin_node is not None:
            latin_node.set("typeface", latin)
        ea_node = font.find("a:ea", ns)
        if ea_node is not None:
            ea_node.set("typeface", cjk)
        cs_node = font.find("a:cs", ns)
        if cs_node is not None:
            cs_node.set("typeface", latin)

    theme_el = root if root.tag == f"{{{A_NS}}}theme" else root.find(".//a:theme", ns)
    if theme_el is not None:
        theme_el.set("name", f"{tokens.NAME} {tokens.VERSION}")

    return etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)


# --------------------------------------------------------------------------- #
# Convenience
# --------------------------------------------------------------------------- #


def build_demo(out_dir: str = "out") -> BuildResult:
    """Build the bundled 12-page reference deck (used by ``deepocean demo``)."""
    from . import examples_data

    deck = spec_mod.Deck.from_dict(examples_data.DEMO_DECK)
    os.makedirs(out_dir, exist_ok=True)
    return build(deck, os.path.join(out_dir, "deep-ocean-demo.pptx"))
