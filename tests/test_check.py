# -*- coding: utf-8 -*-
"""Linter contract: one deliberate violation per rule family, plus a clean deck.

Every fixture is built in memory with python-pptx, so the tests are fast,
deterministic and independent of the layout / build modules.

Run with ``pytest tests/test_check.py`` (or ``python tests/test_check.py`` for
the bundled manual runner, which needs no pytest).
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile

from pptx import Presentation
from pptx.chart.data import CategoryChartData
from pptx.dml.color import RGBColor
from pptx.enum.chart import XL_CHART_TYPE
from pptx.enum.shapes import MSO_CONNECTOR, MSO_SHAPE
from pptx.util import Emu, Inches, Pt

from deepocean import check, spec

# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #

NAVY = RGBColor(0x1B, 0x3A, 0x5C)
TEAL = RGBColor(0x2E, 0x9B, 0xA6)
LIGHT = RGBColor(0xF4, 0xF7, 0xFB)
MINT = RGBColor(0xE6, 0xF3, 0xF5)         # accent tint (#E6F3F5) -> C004
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
HAIRLINE = RGBColor(0xD6, 0xDC, 0xE5)
T2 = RGBColor(0x4A, 0x55, 0x68)
PURPLE = RGBColor(0x8E, 0x44, 0xAD)      # forbidden hue -> C002
NEAR_NAVY = RGBColor(0x1B, 0x3A, 0x5D)   # one step off the palette -> C001
BRICK = RGBColor(0xC0, 0x39, 0x2B)


def tokens_emu(px: float) -> int:
    """Design px -> EMU (the deck is authored on a 1280x720 canvas)."""
    return int(round(px / 96.0 * 914400))


def _blank(prs: Presentation):
    return prs.slides.add_slide(prs.slide_layouts[6])


def _has_yaml() -> bool:
    """PyYAML is an optional extra: .yaml targets need it, .json never does."""
    try:
        import yaml  # noqa: F401
    except ImportError:
        return False
    return True


def _shape(slide, kind, x, y, w, h, fill=None, line=None, line_w=None):
    shape = slide.shapes.add_shape(kind, Emu(tokens_emu(x)), Emu(tokens_emu(y)),
                                   Emu(tokens_emu(w)), Emu(tokens_emu(h)))
    shape.shadow.inherit = False
    if fill is None:
        shape.fill.background()
    else:
        shape.fill.solid()
        shape.fill.fore_color.rgb = fill
    if line is None:
        shape.line.fill.background()
    else:
        shape.line.color.rgb = line
        if line_w:
            shape.line.width = Pt(line_w)
    return shape


def _textbox(slide, x, y, w, h, runs):
    """``runs``: list of ``(text, size_px, RGBColor | None, font name | None, bold)``."""
    box = slide.shapes.add_textbox(Emu(tokens_emu(x)), Emu(tokens_emu(y)),
                                   Emu(tokens_emu(w)), Emu(tokens_emu(h)))
    frame = box.text_frame
    frame.word_wrap = True
    paragraph = frame.paragraphs[0]
    for text, size_px, colour, name, bold in runs:
        run = paragraph.add_run()
        run.text = text
        run.font.size = Pt(size_px * 0.75)
        run.font.bold = bold
        if colour is not None:
            run.font.color.rgb = colour
        if name:
            run.font.name = name
    return box


def clean_presentation() -> Presentation:
    """A minimal, fully compliant one-page deck (no error- or warn-level issue)."""
    prs = Presentation()
    prs.slide_width = Inches(13.3333)
    prs.slide_height = Inches(7.5)
    slide = _blank(prs)

    # Band A: full-bleed chrome, exempt from the side-margin rule
    _shape(slide, MSO_SHAPE.RECTANGLE, 0, 0, 1280, 60, fill=NAVY)
    _textbox(slide, 0, 0, 1280, 60, [("ISR · 2025", 14, WHITE, None, False)])
    # a 1px white sliver keeps the white surface present in the palette stats
    _shape(slide, MSO_SHAPE.RECTANGLE, 0, 0, 1280, 1, fill=WHITE)

    # Band B: title
    _textbox(slide, 40, 72, 1200, 68, [("研究背景", 30, NAVY, None, True)])
    # Band C: a card that reaches y=660 (>= 600) and stays inside 40..1240
    _shape(slide, MSO_SHAPE.ROUNDED_RECTANGLE, 40, 200, 400, 430,
           fill=LIGHT, line=HAIRLINE, line_w=1.0)
    _textbox(slide, 56, 216, 368, 120, [("推荐位改变了消费者搜索路径与品类结构。",
                                         14, T2, None, False)])
    return prs


def merged(*rects):
    """The clean deck plus extra rectangles: ``(x, y, w, h, fill)`` tuples."""

    def extend(prs: Presentation) -> Presentation:
        slide = prs.slides[0]
        for item in rects:
            x, y, w, h = item[:4]
            fill = item[4] if len(item) > 4 else None
            _shape(slide, MSO_SHAPE.RECTANGLE, x, y, w, h, fill=fill)
        return prs

    return extend


def on_clean() -> Presentation:
    return clean_presentation()


def with_text(runs) -> Presentation:
    """The clean deck plus one text box in the lower content band."""
    prs = on_clean()
    _textbox(prs.slides[0], 40, 560, 700, 40, runs)
    return prs


def codes(report: check.Report) -> set:
    return set(report.by_code())


def levels(report: check.Report, code: str) -> set:
    return {issue.level for issue in report.by_code().get(code, [])}


def messages(report: check.Report, code: str) -> str:
    return " | ".join(issue.message for issue in report.by_code().get(code, []))


# -- deck fixtures ---------------------------------------------------------- #
#
# The chrome-only rules read the layout from the deck, so a geometry fixture
# must describe a *content* page.  A separate two-page skeleton covers the
# document-level rules.


def content_deck() -> spec.Deck:
    """One content page -> page 1 of the audited presentation."""
    return spec.Deck.from_dict({
        "meta": {"title": "排版自检"},
        "pages": [{"layout": "two_column", "title": "研究背景",
                   "data": {"left": {"title": "现象"}, "right": [{"title": "缺口"}]}}],
    })


def doc_deck(**overrides) -> spec.Deck:
    """A small but well-formed two-page document (warns about rhythm, no errors)."""
    raw = {
        "meta": {"title": "推荐如何影响消费者搜索"},
        "pages": [
            {"layout": "cover", "title": "封面"},
            {"layout": "two_column", "title": "背景",
             "data": {"left": {"title": "A"}, "right": [{"title": "C"}]}},
        ],
    }
    raw.update(overrides)
    return spec.Deck.from_dict(raw)


# --------------------------------------------------------------------------- #
# The clean deck
# --------------------------------------------------------------------------- #


def test_clean_presentation_has_no_error_or_warn_level_issues():
    report = check.check_pptx(clean_presentation(), content_deck())
    assert report.ok(), report.to_text()
    assert report.errors() == []
    assert report.warnings() == [], report.to_text()
    assert report.target == "Presentation"


def test_clean_presentation_stats_are_populated():
    report = check.check_pptx(clean_presentation(), content_deck())
    stats = report.stats
    for key in ("pages", "hero_pages", "shapes", "palette_colours", "off_palette",
                "brick_share", "min_font_px", "fonts", "error_count", "warn_count"):
        assert key in stats, key
    assert stats["pages"] == 1
    assert stats["shapes"] == 6
    assert stats["error_count"] == 0
    assert stats["warn_count"] == 0
    assert stats["brick_share"] == 0
    assert stats["min_font_px"] == 14.0
    assert stats["palette_colours"] >= 4
    assert isinstance(stats["fonts"], list)
    assert report.to_dict()["ok"] is True


def test_clean_presentation_is_deterministic_and_ordered():
    first = check.check_pptx(clean_presentation(), content_deck()).to_dict()
    second = check.check_pptx(clean_presentation(), content_deck()).to_dict()
    assert json.dumps(first, ensure_ascii=False, sort_keys=True) == \
        json.dumps(second, ensure_ascii=False, sort_keys=True)
    pages = [(issue["page"] is None, issue["page"], issue["code"]) for issue in first["issues"]]
    assert pages == sorted(pages)


def test_repeat_runs_do_not_accumulate_issues():
    report = check.check_pptx(merged((40, 300, 100, 100, PURPLE))(on_clean()), content_deck())
    again = check.check_pptx(merged((40, 300, 100, 100, PURPLE))(on_clean()), content_deck())
    assert len(report.issues) == len(again.issues)
    assert report.by_code()["C002"][0].detail == again.by_code()["C002"][0].detail


# --------------------------------------------------------------------------- #
# Colour rules
# --------------------------------------------------------------------------- #


def test_off_palette_colour_is_reported_with_the_nearest_token():
    report = check.check_pptx(merged((40, 200, 100, 100, NEAR_NAVY))(on_clean()), content_deck())
    assert "C001" in codes(report)
    assert levels(report, "C001") == {"error"}
    assert not report.ok()
    detail = report.by_code()["C001"][0].detail
    assert detail["hex"] == "#1B3A5D"
    assert detail["nearest"] == "navy"
    assert report.stats["off_palette"] == 1


def test_forbidden_colour_is_reported_as_c002_not_c001():
    report = check.check_pptx(merged((40, 200, 100, 100, PURPLE))(on_clean()), content_deck())
    assert "C002" in codes(report)
    assert "C001" not in codes(report)          # forbidden wins, no double report
    assert levels(report, "C002") == {"error"}
    assert "紫" in messages(report, "C002")


def test_brick_share_over_six_percent_warns():
    report = check.check_pptx(merged((40, 500, 600, 200, BRICK))(on_clean()), content_deck())
    assert "C003" in codes(report)
    assert levels(report, "C003") == {"warn"}
    assert report.stats["brick_share"] > 0.06


def test_a_small_brick_accent_is_fine():
    report = check.check_pptx(merged((40, 560, 80, 40, BRICK))(on_clean()), content_deck())
    assert "C003" not in codes(report)
    assert report.ok()


def test_tint_family_over_twenty_percent_warns():
    # Accent tints (mint / pink) carry the 0-20% style-guide budget; the rule is
    # calibrated to a 35% ceiling because a single "撑满" accent card already
    # covers ~30% of the canvas (docs/STYLE.md §9).
    report = check.check_pptx(merged((40, 200, 1100, 440, MINT))(on_clean()), content_deck())
    assert "C004" in codes(report)
    assert levels(report, "C004") == {"warn"}


def test_plain_grey_card_surface_is_not_budgeted_as_an_accent_tint():
    # #F4F7FB is the sanctioned card surface: filling the content band with it is
    # the guide's own instruction, so it must not trip the tint ratio rule.
    report = check.check_pptx(merged((40, 200, 1100, 440, LIGHT))(on_clean()), content_deck())
    assert "C004" not in codes(report)


def test_dark_page_area_is_an_info_not_an_error():
    report = check.check_pptx(merged((40, 200, 1000, 400, NAVY))(on_clean()), content_deck())
    assert "C005" in codes(report)
    assert levels(report, "C005") == {"info"}
    assert report.ok()


def test_low_contrast_body_text_warns_but_large_display_text_does_not():
    low = with_text([("低对比度正文文字在此", 14, TEAL, None, False)])
    assert "K001" in codes(check.check_pptx(low, content_deck()))

    big = with_text([("主效应", 48, TEAL, None, True)])
    assert "K001" not in codes(check.check_pptx(big, content_deck()))


# --------------------------------------------------------------------------- #
# Typography rules
# --------------------------------------------------------------------------- #


def test_text_below_eleven_px_is_an_error():
    report = check.check_pptx(with_text([("极小字号", 8, T2, None, False)]), content_deck())
    assert "T001" in codes(report)
    assert levels(report, "T001") == {"error"}
    assert report.stats["min_font_px"] == 8.0


def test_body_copy_between_eleven_and_thirteen_px_is_an_error():
    # Running body copy is prose that wraps to two or more lines inside its box;
    # one-line captions at the same size stay legal (next test).
    long_text = ("这是一段明显属于正文的内容，用于验证字号下限判定逻辑是否生效；"
                 "这里继续补充更多文字，确保它在自己的文本框里换成两行以上。")
    report = check.check_pptx(with_text([(long_text, 12, T2, None, False)]), content_deck())
    assert "T002" in codes(report)
    assert levels(report, "T002") == {"error"}
    assert "T001" not in codes(report)          # 12px is above the hard floor


def test_short_caption_at_twelve_px_is_allowed():
    report = check.check_pptx(with_text([("来源：ISR 2025", 12, T2, None, False)]), content_deck())
    assert "T001" not in codes(report)
    assert "T002" not in codes(report)


def test_more_than_two_font_families_warns():
    report = check.check_pptx(with_text([
        ("Group meeting review 2026", 14, T2, "Times New Roman", False),
        ("Second family on the same page", 14, T2, "Courier New", False),
    ]), content_deck())
    assert "T003" in codes(report)
    assert levels(report, "T003") == {"warn"}
    assert len(report.by_code()["T003"][0].detail["fonts"]) > 2


def test_more_than_two_font_weights_warns():
    two = on_clean()
    _textbox(two.slides[0], 40, 560, 700, 40, [("Bold", 14, T2, None, True)])
    _textbox(two.slides[0], 40, 610, 700, 40, [("Regular", 14, T2, None, False)])
    assert "T004" not in codes(check.check_pptx(two, content_deck()))

    three = on_clean()
    bold = _textbox(three.slides[0], 40, 560, 700, 40, [("Bold", 14, T2, None, True)])
    bold.text_frame.paragraphs[0].runs[0].font.italic = True           # bold+italic
    italic = _textbox(three.slides[0], 40, 610, 700, 40, [("Italic", 14, T2, None, False)])
    italic.text_frame.paragraphs[0].runs[0].font.italic = True         # italic only
    _textbox(three.slides[0], 40, 655, 700, 40, [("Regular", 14, T2, None, False)])

    report = check.check_pptx(three, content_deck())
    assert "T004" in codes(report)
    assert levels(report, "T004") == {"warn"}
    assert {"bold+italic", "italic"} <= set(report.by_code()["T004"][0].detail["weights"])


def test_text_overflow_beyond_fifteen_percent_warns():
    prs = on_clean()
    _textbox(prs.slides[0], 40, 560, 200, 14, [
        ("这是一段很长的文字，用来把文本框彻底撑爆，从而触发溢出的告警判定。", 30, T2, None, False)])
    report = check.check_pptx(prs, content_deck())
    assert "T005" in codes(report)
    assert levels(report, "T005") == {"warn"}
    detail = report.by_code()["T005"][0].detail
    assert detail["needed_px"] > detail["box_h"] * 1.15


# --------------------------------------------------------------------------- #
# Geometry rules
# --------------------------------------------------------------------------- #


def test_shape_outside_the_left_safe_margin_is_an_error():
    report = check.check_pptx(merged((10, 300, 100, 100, LIGHT))(on_clean()), content_deck())
    assert "M001" in codes(report)
    assert levels(report, "M001") == {"error"}
    assert report.by_code()["M001"][0].detail["x"] == 10.0


def test_shape_reaching_past_the_right_margin_is_an_error():
    report = check.check_pptx(merged((1150, 300, 200, 100, LIGHT))(on_clean()), content_deck())
    assert "M001" in codes(report)
    assert report.by_code()["M001"][0].detail["right"] > 1240


def test_full_width_chrome_is_exempt_from_the_side_margin():
    report = check.check_pptx(clean_presentation(), content_deck())
    assert "M001" not in codes(report)          # the top bar spans 0..1280


def test_overlapping_the_reserved_top_bar_strip_is_an_error():
    report = check.check_pptx(merged((200, 64, 300, 40, LIGHT))(on_clean()), content_deck())
    assert "M002" in codes(report)
    assert levels(report, "M002") == {"error"}
    assert report.by_code()["M002"][0].detail["y"] == 64.0


def test_a_shape_touching_but_not_overlapping_the_strip_is_fine():
    report = check.check_pptx(merged((200, 72, 300, 40, LIGHT))(on_clean()), content_deck())
    assert "M002" not in codes(report)


def test_shape_past_the_canvas_is_an_info():
    # 40..1240 wide, but it runs off the bottom edge: only M004 applies
    report = check.check_pptx(merged((40, 600, 400, 200, NAVY))(on_clean()), content_deck())
    assert "M004" in codes(report)
    assert levels(report, "M004") == {"info"}
    assert levels(report, "M001") == set()
    assert report.ok()                          # info never fails the deck


def test_content_that_does_not_fill_the_page_warns():
    prs = clean_presentation()
    prs.slides[0].shapes[4].height = Emu(tokens_emu(200))     # card now ends at y=400
    report = check.check_pptx(prs, content_deck())
    assert "M003" in codes(report)
    assert levels(report, "M003") == {"warn"}
    assert report.by_code()["M003"][0].detail["max_bottom"] < 600


def test_missing_visual_anchor_is_an_info():
    prs = clean_presentation()
    prs.slides[0].shapes[4].width = Emu(tokens_emu(100))      # card << 40% of the band
    report = check.check_pptx(prs, content_deck())
    assert "A001" in codes(report)
    assert levels(report, "A001") == {"info"}


# --------------------------------------------------------------------------- #
# Chart rules
# --------------------------------------------------------------------------- #


def _chart_prs(height_px: float = 300) -> Presentation:
    prs = clean_presentation()
    data = CategoryChartData()
    data.categories = ["A", "B", "C"]
    data.add_series("S1", (1, 2, 3))
    data.add_series("S2", (4, 5, 6))
    prs.slides[0].shapes.add_chart(
        XL_CHART_TYPE.COLUMN_CLUSTERED, Emu(tokens_emu(460)), Emu(tokens_emu(200)),
        Emu(tokens_emu(780)), Emu(tokens_emu(height_px)), data)
    return prs


def test_chart_without_data_labels_warns():
    from pptx.oxml.ns import qn

    prs = _chart_prs()
    series = list(prs.slides[0].shapes[-1].chart.plots)[0].series[1]
    element = series.data_labels._element            # creates <c:dLbls/>
    element.insert(0, element.makeelement(qn("c:delete"), {"val": "1"}))
    report = check.check_pptx(prs, content_deck())
    assert "H001" in codes(report)
    assert levels(report, "H001") == {"warn"}


def test_chart_level_labels_off_flags_every_series():
    from pptx.oxml.ns import qn

    prs = _chart_prs()
    plot = list(prs.slides[0].shapes[-1].chart.plots)[0]
    plot.has_data_labels = True
    element = plot.data_labels._element
    element.insert(0, element.makeelement(qn("c:delete"), {"val": "1"}))
    report = check.check_pptx(prs, content_deck())
    assert "H001" in codes(report)
    assert levels(report, "H001") == {"warn"}


def test_chart_with_data_labels_is_clean():
    prs = _chart_prs()
    for series in list(prs.slides[0].shapes[-1].chart.plots)[0].series:
        series.data_labels.show_value = True
    report = check.check_pptx(prs, content_deck())
    assert "H001" not in codes(report)


def test_chart_with_zero_height_is_an_error():
    prs = _chart_prs()
    prs.slides[0].shapes[-1].height = Emu(0)
    report = check.check_pptx(prs, content_deck())
    assert "H002" in codes(report)
    assert levels(report, "H002") == {"error"}
    assert not report.ok()


# --------------------------------------------------------------------------- #
# Odd shapes must never crash the linter
# --------------------------------------------------------------------------- #


def test_group_connector_and_table_do_not_crash():
    prs = clean_presentation()
    slide = prs.slides[0]
    group = slide.shapes.add_group_shape()
    group.shapes.add_shape(MSO_SHAPE.RECTANGLE, Emu(tokens_emu(40)), Emu(tokens_emu(600)),
                           Emu(tokens_emu(100)), Emu(tokens_emu(40)))
    connector = slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT,
                                           Emu(tokens_emu(40)), Emu(tokens_emu(500)),
                                           Emu(tokens_emu(400)), Emu(tokens_emu(500)))
    connector.line.color.rgb = TEAL
    table = slide.shapes.add_table(3, 3, Emu(tokens_emu(460)), Emu(tokens_emu(200)),
                                   Emu(tokens_emu(500)), Emu(tokens_emu(200))).table
    table.cell(0, 0).text = "指标"
    table.cell(1, 0).text = "搜索量"
    report = check.check_pptx(prs, content_deck())
    assert isinstance(report, check.Report)
    assert report.stats["shapes"] >= 10
    assert group is not None and table is not None


def test_a_degenerate_connector_is_skipped_without_raising():
    prs = clean_presentation()
    connector = prs.slides[0].shapes.add_connector(
        MSO_CONNECTOR.STRAIGHT, Emu(0), Emu(0), Emu(0), Emu(0))
    report = check.check_pptx(prs, content_deck())
    assert isinstance(report, check.Report)
    assert connector is not None
    assert report.ok()


def test_picture_shape_is_measured():
    import io as _io
    import struct
    import zlib

    def tiny_png() -> bytes:
        def chunk(tag: bytes, payload: bytes) -> bytes:
            body = tag + payload
            return struct.pack(">I", len(payload)) + body + struct.pack(">I", zlib.crc32(body))

        header = struct.pack(">IIBBBBB", 1, 1, 8, 6, 0, 0, 0)
        raw = b"\x00" + bytes((0x1B, 0x3A, 0x5C, 0xFF))
        return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header)
                + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))

    prs = clean_presentation()
    prs.slides[0].shapes.add_picture(_io.BytesIO(tiny_png()), Emu(tokens_emu(460)),
                                     Emu(tokens_emu(420)), Emu(tokens_emu(200)),
                                     Emu(tokens_emu(120)))
    report = check.check_pptx(prs, content_deck())
    assert isinstance(report, check.Report)
    assert report.stats["shapes"] == 7


# --------------------------------------------------------------------------- #
# Document-level rules (check_deck)
# --------------------------------------------------------------------------- #


def test_check_deck_accepts_a_well_formed_document():
    report = check.check_deck(doc_deck())
    assert report.errors() == [], report.to_text()
    assert report.ok()
    assert report.target == "推荐如何影响消费者搜索"
    # two pages is legitimately below the calibrated count; nothing else fires
    assert {i.code for i in report.issues} == {"R001", "R002", "R006"}


def test_d001_empty_deck_is_an_error():
    report = check.check_deck(spec.Deck(meta=spec.DeckMeta(title="t"), pages=[]))
    assert "D001" in codes(report)
    assert levels(report, "D001") == {"error"}
    assert report.stats["pages"] == 0
    assert not report.ok()


def test_d002_missing_meta_title_is_an_error():
    report = check.check_deck(spec.Deck(meta=spec.DeckMeta(title=""), pages=[
        spec.Page.from_dict({"layout": "cover", "title": "封面"})]))
    assert "D002" in codes(report)
    assert levels(report, "D002") == {"error"}


def test_l001_unknown_layout_and_alias_are_errors():
    unknown = check.check_deck(spec.Deck.from_dict({
        "meta": {"title": "t"},
        "pages": [{"layout": "mystery", "title": "x"}]}))
    assert "L001" in codes(unknown)
    assert levels(unknown, "L001") == {"error"}

    alias = check.check_deck(spec.Deck.from_dict({
        "meta": {"title": "t"},
        "pages": [{"layout": "chart", "title": "x"}]}))
    assert "L001" in codes(alias)
    assert alias.by_code()["L001"][0].detail["canonical"] == "chart_insight"


def test_l002_missing_required_field_is_an_error():
    deck = spec.Deck.from_dict({
        "meta": {"title": "t"},
        "pages": [{"layout": "two_column", "title": "只有左栏", "data": {"left": {"title": "A"}}}]})
    report = check.check_deck(deck)
    assert "L002" in codes(report)
    assert levels(report, "L002") == {"error"}
    assert "right" in messages(report, "L002")


def test_l003_missing_title_on_a_content_page_warns():
    deck = spec.Deck.from_dict({
        "meta": {"title": "t"},
        "pages": [{"layout": "two_column", "data": {"left": {"title": "A"}, "right": []}}]})
    report = check.check_deck(deck)
    assert "L003" in codes(report)
    assert levels(report, "L003") == {"warn"}
    assert report.by_code()["L003"][0].page == 1


def test_x001_placeholder_text_is_an_error_in_any_field():
    for marker in ("lorem ipsum dolor", "TODO", "待填", "占位", "PLACEHOLDER"):
        deck = spec.Deck.from_dict({
            "meta": {"title": "t"},
            "pages": [{"layout": "two_column", "title": "背景",
                       "data": {"left": {"title": "A", "body": marker},
                                "right": [{"title": "C"}]}}]})
        report = check.check_deck(deck)
        assert "X001" in codes(report), marker
        assert levels(report, "X001") == {"error"}, marker
        assert report.by_code()["X001"][0].detail["marker"].lower() in marker.lower()


def test_x002_empty_field_warns():
    deck = spec.Deck.from_dict({
        "meta": {"title": "t"},
        "pages": [{"layout": "chart_insight", "title": "主效应",
                   "data": {"chart": {"type": "bar", "height": 300}, "kpis": ""}}]})
    report = check.check_deck(deck)
    assert "X002" in codes(report)
    assert levels(report, "X002") == {"warn"}
    assert report.by_code()["X002"][0].detail["field"] == "kpis"


def test_r001_page_count_outside_the_calibrated_band_warns():
    report = check.check_deck(doc_deck())
    assert "R001" in codes(report)
    assert levels(report, "R001") == {"warn"}
    assert report.by_code()["R001"][0].page is None


def test_r002_hero_ratio_outside_the_band_warns():
    single = spec.Deck.from_dict({"meta": {"title": "t"},
                                 "pages": [{"layout": "cover", "title": "封面"}]})
    report = check.check_deck(single)
    assert "R002" in codes(report)
    assert report.stats["hero_pages"] == 1
    assert report.by_code()["R002"][0].detail["ratio"] == 1.0
    # 1 hero out of 2 pages is 50% -> outside the band (the band is 25-45%)
    assert "R002" in codes(check.check_deck(doc_deck()))

    # This also pins the actual hero set from tokens.HERO_LAYOUTS
    # (cover / key_findings / closing) against the rhythm budget.
    def content(i: int) -> dict:
        return {"layout": "matrix2x2", "title": f"机制{i}",
                "data": {"aside": {"title": "维度"}, "quadrants": [{"no": "1"}]}}

    def peak(i: int) -> dict:
        return {"layout": "key_findings", "title": f"峰值{i}",
                "data": {"banner": {"heading": "结论"}, "cards": [{"title": "A"}]}}

    pages = [{"layout": "cover", "title": "封面"}]
    for index in range(11):
        if index in (2, 6, 10):                      # pages 3, 7, 11 are peaks
            pages.append(peak(index))
        else:
            pages.append(content(index))
    report = check.check_deck(spec.Deck.from_dict({"meta": {"title": "t"}, "pages": pages}))
    assert report.stats["hero_pages"] == 4          # cover + 3 key_findings
    assert report.stats["pages"] == 12
    assert report.stats["hero_pages"] / 12 == 1 / 3  # exactly inside the band
    assert "R002" not in codes(report), report.to_text()


def test_r003_three_consecutive_non_hero_pages_warn():
    pages = [{"layout": "two_column", "title": f"页{i}",
              "data": {"left": {"title": "A"}, "right": [{"title": "C"}]}}
             for i in range(1, 4)]
    report = check.check_deck(spec.Deck.from_dict({"meta": {"title": "t"}, "pages": pages}))
    assert "R003" in codes(report)
    assert report.by_code()["R003"][0].detail["pages"] == [1, 2, 3]


def test_r003_is_silent_when_a_hero_page_breaks_the_run():
    pages = [{"layout": "two_column", "title": "A", "data": {"left": {"title": "x"}, "right": []}},
             {"layout": "two_column", "title": "B", "data": {"left": {"title": "x"}, "right": []}},
             {"layout": "cover", "title": "封面"},
             {"layout": "two_column", "title": "C", "data": {"left": {"title": "x"}, "right": []}}]
    report = check.check_deck(spec.Deck.from_dict({"meta": {"title": "t"}, "pages": pages}))
    assert "R003" not in codes(report)


def test_r004_adjacent_identical_layouts_warn():
    pages = [{"layout": "two_column", "title": "A", "data": {"left": {"title": "x"}, "right": []}},
             {"layout": "two_column", "title": "B", "data": {"left": {"title": "x"}, "right": []}}]
    report = check.check_deck(spec.Deck.from_dict({"meta": {"title": "t"}, "pages": pages}))
    assert "R004" in codes(report)
    assert report.by_code()["R004"][0].page == 2
    assert report.by_code()["R004"][0].detail["previous_page"] == 1


def test_r005_more_than_two_equal_width_rows_warn():
    pages = [{"layout": "big_number", "title": f"数字{i}",
              "data": {"mode": "grid", "items": [{"number": "1"}]}} for i in range(1, 4)]
    report = check.check_deck(spec.Deck.from_dict({"meta": {"title": "t"}, "pages": pages}))
    assert "R005" in codes(report)
    assert report.by_code()["R005"][0].detail["pages"] == [1, 2, 3]


def test_r005_is_silent_for_a_single_data_table():
    deck = spec.Deck.from_dict({
        "meta": {"title": "t"},
        "pages": [{"layout": "cover", "title": "封面"},
                  {"layout": "chart_insight", "title": "主效应",
                   "data": {"chart": {"type": "bar", "height": 300}}},
                  {"layout": "data_table", "title": "数据表",
                   "data": {"columns": ["a"], "rows": [["1"]]}}]})
    report = check.check_deck(deck)
    assert "R005" not in codes(report)
    assert "R006" not in codes(report)          # the chart page is the evidence page


def test_r006_missing_evidence_page_warns():
    report = check.check_deck(doc_deck())
    assert "R006" in codes(report)
    assert levels(report, "R006") == {"warn"}


def test_document_report_stats():
    report = check.check_deck(doc_deck())
    assert report.stats["pages"] == 2
    assert report.stats["hero_pages"] == 1
    assert report.stats["error_count"] == 0
    assert report.stats["warn_count"] == len(report.warnings())
    assert report.stats["shapes"] == 0
    assert report.ok()                          # warns only


# --------------------------------------------------------------------------- #
# Report rendering
# --------------------------------------------------------------------------- #


def test_report_text_is_grouped_by_page_and_ordered():
    deck = spec.Deck.from_dict({
        "meta": {"title": "t"},
        "pages": [{"layout": "mystery", "title": "x"},
                  {"layout": "two_column", "data": {"left": {"title": "A"}, "right": []}}]})
    report = check.check_deck(deck)
    text = report.to_text()
    assert "Deep Ocean 自检" in text
    assert "结果：" in text
    assert "第01页" in text
    assert "第02页" in text
    assert text.index("第01页") < text.index("第02页")
    assert "统计：" in text
    assert "pages = 2" in text

    coloured = report.to_text(color=True)
    assert "\033[" in coloured
    assert "第01页" in coloured


def test_report_by_code_counts_and_json():
    report = check.check_deck(doc_deck())
    grouped = report.by_code()
    assert isinstance(grouped, dict)
    assert set(grouped) <= set(check.RULE_CODES)
    counts = report.counts()
    assert counts["error"] == len(report.errors())
    assert counts["warn"] == len(report.warnings())
    assert counts["info"] == len(report.infos())
    payload = report.to_dict()
    assert json.dumps(payload, ensure_ascii=False)         # must be serialisable
    assert payload["ok"] == report.ok()
    assert payload["target"] == report.target
    for issue in payload["issues"]:
        assert set(issue) == {"level", "code", "message", "page", "detail"}
        assert issue["level"] in ("error", "warn", "info")
        assert issue["code"] in check.RULE_CODES
        assert issue["message"].strip()


def test_issue_defaults_and_sort_key():
    issue = check.Issue("nonsense", "C001", "信息", None, {})
    assert issue.level == "warn"                 # invalid level degrades safely
    assert issue.page is None
    assert check.Issue("error", "D001", "m", "3").page == 3
    assert check.Issue("error", "D001", "m", None).sort_key[0] == -1
    assert check.Issue("error", "D001", "m", 1).to_text().startswith("[D001] 第 01 页")


def test_rule_codes_and_table_cover_every_code():
    assert len(check.RULE_CODES) == 31
    assert all(value.strip().endswith("。") for value in check.RULE_CODES.values())
    table = check.rule_table()
    lines = table.splitlines()
    assert lines[0] == "| code | level | rule | guide section |"
    assert lines[1] == "| --- | --- | --- | --- |"
    assert len(lines) == 2 + len(check.RULE_CODES)
    seen = []
    for line in lines[2:]:
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        assert len(cells) == 4, line
        code = cells[0].strip("`")
        assert code in check.RULE_CODES
        assert cells[1] in ("error", "warn", "info")
        assert cells[2] and cells[3]
        seen.append(code)
    assert set(seen) == set(check.RULE_CODES)
    # families appear in guide order: document, layout, rhythm, text, geometry...
    assert seen.index("D001") < seen.index("L001") < seen.index("R001")
    assert seen.index("R001") < seen.index("X001") < seen.index("M001") < seen.index("T001")
    assert seen.index("T001") < seen.index("C001") < seen.index("K001") < seen.index("A001")
    assert seen.index("A001") < seen.index("H001")


def test_families_reported_are_documented_and_ordered_by_page_then_code():
    report = check.check_pptx(merged((10, 300, 100, 100, PURPLE))(on_clean()), content_deck())
    assert report.by_code()
    for code in report.by_code():
        assert code in check.RULE_CODES, code
    # page first, then rule family (document < layout < rhythm < geometry < type
    # < colour < contrast < anchor < charts), which is the checklist's own order
    pages = [(issue.page, issue.sort_key[1]) for issue in report.issues]
    assert pages == sorted(pages, key=lambda item: (item[0] is None, item[0], item[1]))
    codes_seen = [issue.code for issue in report.issues]
    assert codes_seen.index("M001") < codes_seen.index("C002") < codes_seen.index("A001")


# --------------------------------------------------------------------------- #
# Dispatch
# --------------------------------------------------------------------------- #


def test_check_dispatches_on_suffix_and_instances():
    with tempfile.TemporaryDirectory(prefix="deepocean-check-") as tmp:
        deck = doc_deck()
        json_path = os.path.join(tmp, "deck.json")
        deck.save(json_path)
        via_json = check.check(json_path)
        assert isinstance(via_json, check.Report)
        assert via_json.stats["pages"] == 2
        assert via_json.target == "deck.json"

        pptx_path = os.path.join(tmp, "deck.pptx")
        clean_presentation().save(pptx_path)
        via_pptx = check.check(pptx_path)
        assert via_pptx.target == "deck.pptx"
        assert via_pptx.stats["pages"] == 1

    assert check.check(deck).target == deck.meta.title
    assert check.check(clean_presentation()).stats["pages"] == 1


def test_yaml_target_needs_pyyaml_or_works():
    deck = doc_deck()
    path = os.path.join(tempfile.gettempdir(), "deepocean-dispatch-probe.yaml")
    try:
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(deck.to_dict(), handle, ensure_ascii=False)
        if _has_yaml():
            assert check.check(path).stats["pages"] == 2
        else:
            try:
                check.check(path)
            except spec.SpecError as exc:
                assert "PyYAML" in str(exc)      # documented, actionable failure
            else:
                raise AssertionError("a .yaml target must need PyYAML")
    finally:
        if os.path.exists(path):
            os.remove(path)


def test_check_pptx_accepts_a_path():
    tmp = tempfile.mkdtemp(prefix="deepocean-check-")
    try:
        path = os.path.join(tmp, "clean.pptx")
        clean_presentation().save(path)
        report = check.check_pptx(path, content_deck())
        assert report.target == "clean.pptx"
        assert report.ok(), report.to_text()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_check_pptx_on_a_missing_file_reports_instead_of_raising():
    report = check.check_pptx(os.path.join(tempfile.gettempdir(), "definitely-missing.pptx"))
    assert isinstance(report, check.Report)
    assert report.stats["pages"] == 0


def test_linter_is_importable_from_the_package_namespace():
    import deepocean

    assert deepocean.check is check                       # lazy __getattr__ path
    assert deepocean.check.rule_table() == check.rule_table()


def test_check_module_does_not_import_the_renderers():
    """Guards the import graph: the linter must stay free of cycles."""
    with open(check.__file__, encoding="utf-8") as handle:
        source = handle.read()
    head = source.split('"""', 2)[2]                      # ignore the module docstring
    for forbidden in ("from .layouts", "from .build", "from .components",
                      "from .charts", "from .html"):
        assert forbidden not in head, forbidden
    for allowed in ("from . import primitives", "schema, spec, tokens"):
        assert allowed in head, allowed


if __name__ == "__main__":  # pragma: no cover - manual runner fallback
    import inspect as _inspect

    passed = failed = 0
    for name, fn in sorted(list(globals().items())):
        if not name.startswith("test_") or not callable(fn):
            continue
        try:
            if list(_inspect.signature(fn).parameters):   # pytest-only fixtures
                continue
            fn()
            passed += 1
        except AssertionError as exc:
            failed += 1
            print(f"FAIL {name}: {exc}")
    print(f"test_check: {passed} tests passed, {failed} failed (manual runner)")
    if failed:
        raise SystemExit(1)
