# -*- coding: utf-8 -*-
"""Tests for the HTML / print renderer (:mod:`deepocean.html`).

The renderer is deterministic string assembly, so these tests assert on the
emitted markup: the 1280x720 canvas, the four bands, the page number, the
inline SVG charts, the print block and the escaping rules.  No PyYAML needed —
decks are built from plain dicts.
"""

from __future__ import annotations

import os
import re

from deepocean import html as do_html
from deepocean import schema, spec, tokens

PAGE = '<section class="do-page"'


def _deck_dict():
    return {
        "meta": {
            "title": "推荐如何影响消费者搜索",
            "kicker": "组会文献汇报",
            "journal": "ISR · 2025",
            "authors": ["Yuan", "Chen"],
            "source_note": "组会文献汇报 · ISR 2025",
        },
        "pages": [
            {
                "layout": "cover",
                "title": "推荐如何影响消费者搜索",
                "data": {"english_title": "How Recommendation Affects Customer Search",
                         "series": "ISR · 2025", "note": "样本 555,800",
                         "band": "DEEP OCEAN"},
            },
            {
                "layout": "two_column",
                "kicker": "01 · BACKGROUND",
                "title": "研究背景",
                "subtitle": "推荐与搜索的关系尚无定论",
                "data": {
                    "ratio": 0.60,
                    "left": {"title": "互补还是替代？", "tone": "tint",
                             "body": "第一段\n- 要点一\n- 要点二", "footer": "Table 1"},
                    "right": [{"title": "平台", "body": "头部电商平台"},
                              {"title": "缺口", "tone": "primary", "body": "缺少因果对比"}],
                },
            },
            {
                "layout": "chart_insight",
                "kicker": "02 · MAIN EFFECT",
                "title": "主效应",
                "data": {
                    "chart": {"type": "bar", "title": "各渠道变化", "unit": "%",
                              "categories": ["浏览 PV", "点击"],
                              "series": [{"name": "推荐", "values": [-33.4, -83.6]},
                                         {"name": "搜索", "values": [7.1, 6.3]}],
                              "note": "Table 1"},
                    "kpis": [{"label": "推荐 PV", "value": "−33.4", "unit": "%", "tone": "down"}],
                    "takeaway": {"label": "结论", "text": "搜索只能部分补偿。"},
                },
            },
            {"layout": "data_table", "title": "数值汇总",
             "data": {"columns": ["指标", "推荐"], "rows": [["浏览 PV", "−33.4%"]],
                      "caption": "Table 1", "highlight_col": 1}},
            {"layout": "closing", "title": "总结与展望",
             "data": {"quote": {"text": "一句话结论", "source": "ISR 2025"},
                      "panels": [{"title": "局限", "body": "单平台"},
                                 {"title": "未来", "tone": "primary", "body": "长期追踪"}],
                      "thanks": "Q & A"}},
        ],
    }


def deck():
    return spec.Deck.from_dict(_deck_dict())


# --------------------------------------------------------------------------- #
# API surface
# --------------------------------------------------------------------------- #


def test_public_api_surface():
    for name in ("render", "write", "render_page", "render_fragment", "css"):
        assert callable(getattr(do_html, name))


def test_render_is_one_self_contained_document():
    text = do_html.render(deck())
    assert text.startswith("<!DOCTYPE html>")
    assert text.rstrip().endswith("</html>")
    assert "<style>" in text and "--do-navy:#1B3A5C;" in text
    assert text.count(PAGE) == 5
    assert "cdn" not in text.lower() and "<script" not in text.lower()


def test_render_page_and_fragment_agree():
    d = deck()
    fragment = do_html.render_fragment(d)
    assert fragment.count(PAGE) == 5
    assert "<style>" not in fragment
    assert do_html.render(d, standalone=False) == fragment
    one = do_html.render_page(d.pages[1], d, 2, 5)
    assert one.startswith('<section class="do-page"')
    assert 'data-layout="two_column"' in one
    assert one in fragment


def test_write_returns_absolute_path(tmp_path):
    target = tmp_path / "nested" / "deck.html"
    path = do_html.write(deck(), str(target))
    assert os.path.isabs(path)
    assert os.path.isfile(path)
    with open(path, "r", encoding="utf-8") as handle:
        assert handle.read().count(PAGE) == 5


def test_output_is_deterministic():
    assert do_html.render(deck()) == do_html.render(deck())


# --------------------------------------------------------------------------- #
# Geometry, chrome, accessibility
# --------------------------------------------------------------------------- #


def test_canvas_and_band_geometry():
    text = do_html.render(deck())
    sheet = do_html.css().replace(" ", "")               # ignore CSS whitespace
    assert "width:1280px;height:720px" in sheet          # canvas
    assert "top:680px" in sheet                          # footer rule
    assert "right:40px" in sheet                         # page number -> x=1240
    assert "left:40px" in sheet                          # side margin
    assert "top:410px" in sheet                          # cover divider (guide)
    assert "top:568px" in sheet                          # cover info strip
    assert "top:712px" in sheet                          # bottom navy band
    assert "top:140px" in sheet                          # cover kicker (band B start)
    assert "do-cover-title" in text and "do-cover-strip" in text


def test_page_number_and_footer_note():
    text = do_html.render(deck())
    assert '<div class="do-page-number">03 / 05</div>' in text
    assert '<div class="do-page-number">05 / 05</div>' in text
    assert deck().resolved_footer_note() in text


def test_semantic_sections_and_headings():
    text = do_html.render(deck())
    assert text.count('aria-label="第 ') == 5
    assert 'aria-label="第 1 页 封面' in text
    assert "<h1" in text and "<h2" in text and "<h3" in text


def test_cover_and_closing_are_chrome_exempt():
    d = deck()
    cover = do_html.render_page(d.pages[0], d, 1, 5)
    closing = do_html.render_page(d.pages[4], d, 5, 5)
    assert "do-titleblock" not in cover and "do-page-number" not in cover
    assert "do-close-title" in closing and "do-page-number" in closing


# --------------------------------------------------------------------------- #
# Escaping and text handling
# --------------------------------------------------------------------------- #


def test_escaping_and_newline_handling():
    d = spec.Deck.from_dict({
        "meta": {"title": "<script>alert(1)</script>"},
        "pages": [{"layout": "two_column", "title": "<b>注入</b>",
                   "data": {"left": {"body": "<img src=x onerror=alert(1)>\n- 甲\n- 乙"}}}]})
    text = do_html.render(d)
    assert "<script>alert" not in text
    assert "&lt;script&gt;" in text and "&lt;img" in text and "&lt;b&gt;" in text
    assert "<li>甲</li>" in text and "<li>乙</li>" in text


def test_no_placeholder_artifacts():
    text = do_html.render(deck())
    for bad in ("None", "{}", "[object", "NaN", "Undefined"):
        assert bad not in text


# --------------------------------------------------------------------------- #
# Layouts and charts
# --------------------------------------------------------------------------- #


def test_every_layout_renders_with_empty_data():
    pages = [{"layout": name, "title": "空页"} for name in schema.LAYOUT_NAMES]
    text = do_html.render(spec.Deck.from_dict({"meta": {"title": "bare"}, "pages": pages}))
    assert text.count(PAGE) == len(schema.LAYOUT_NAMES)
    for name in schema.LAYOUT_NAMES:
        assert f'data-layout="{name}"' in text


def test_unknown_layout_degrades_without_raising():
    d = spec.Deck.from_dict({"meta": {"title": "odd"},
                             "pages": [{"layout": "no_such_layout", "title": "未知"}]})
    text = do_html.render(d)
    assert PAGE in text and "未知版式" in text


def test_bar_chart_is_inline_svg_with_value_labels():
    d = deck()
    page = d.pages[2]
    text = do_html.render_page(page, d, 3, 5)
    assert '<svg class="do-chart"' in text
    assert text.count("<rect") >= 4                       # grouped bars
    assert "−33.4" in text and "7.1" in text              # value labels on
    assert "浏览 PV" in text                              # axis label


def test_line_and_doughnut_charts():
    d = spec.Deck.from_dict({
        "meta": {"title": "charts"},
        "pages": [
            {"layout": "chart_insight", "title": "line", "data": {"chart": {
                "type": "line", "categories": ["a", "b", "c"],
                "series": [{"name": "s", "values": [1, 2, 3]}]}}},
            {"layout": "chart_insight", "title": "ring", "data": {"chart": {
                "type": "doughnut", "categories": ["x", "y"],
                "series": [{"name": "share", "values": [70, 30]}]}}},
        ]})
    text = do_html.render(d)
    assert "<polyline" in text and "do-point" in text
    assert '<path d="M' in text and " A" in text          # arc segments
    assert "do-center-v" in text                          # centre label


def test_chart_without_series_shows_placeholder():
    d = spec.Deck.from_dict({"meta": {"title": "x"}, "pages": [
        {"layout": "chart_insight", "title": "空图", "data": {"chart": {"type": "bar"}}}]})
    assert "暂无数据" in do_html.render(d)


# --------------------------------------------------------------------------- #
# Stylesheet / print
# --------------------------------------------------------------------------- #


def test_css_comes_from_tokens():
    sheet = do_html.css()
    assert "--do-navy:#1B3A5C;" in sheet
    assert f"--do-page_title:{tokens.TYPE_SCALE['page_title'].px}px;" in sheet
    assert "--do-font-cjk:" in sheet
    assert "--do-margin:40px;" in sheet


def test_print_block_and_responsive_preview():
    sheet = do_html.css()
    assert "@page { size: 1280px 720px; margin: 0; }" in sheet
    assert "@media print" in sheet
    assert "print-color-adjust: exact" in sheet
    assert "zoom:" in sheet and "@media screen" in sheet
    assert "#EEF1F5" in sheet                             # neutral backdrop
    assert "do-toolbar" in do_html.render(deck())
