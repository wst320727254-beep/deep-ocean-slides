# -*- coding: utf-8 -*-
"""Tests for the paper -> digest -> deck pipeline.

Everything here is offline: no PDF is opened and no model is called.  The real
PDF run is the acceptance test in ``docs/TUTORIAL.md`` (路线 F).
"""

from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from deepocean import author, paper, schema, spec  # noqa: E402


# --------------------------------------------------------------------------- #
# fixtures
# --------------------------------------------------------------------------- #


def make_digest() -> paper.Digest:
    sections = [
        paper.Section("abstract", "Abstract", 1,
                      "本文研究生成式人工智能与人类智能的关系。我们设计了一系列实验，"
                      "覆盖认知、情感、社交与创造四个维度，样本 N = 1,024 名被试。"),
        paper.Section("introduction", "1. Introduction", 2,
                      "生成式人工智能在近两年迅速普及，改变了大量知识型工作。"
                      "然而既有研究很少系统比较它与人类智能的差异。"),
        paper.Section("method", "4.1. Methodology", 14,
                      "我们招募本科生与 GPT-4 参与同一套量表测试。"
                      "每个维度包含若干题目，采用七点量表作答。"),
        paper.Section("results", "5. Results", 36,
                      "本科生在认知维度领先 13.85 分（p < 0.001）。"
                      "情感与社会维度差距较小，创造维度没有显著差异。"),
    ]
    figures = [
        paper.Figure(page=7, index=1, width=1200, height=900, path="figures/p07-fig01.png",
                     bytes_=90_000, caption="Figure 1 Proposed Framework for Understanding LLM"),
        paper.Figure(page=27, index=1, width=7984, height=5956, path="figures/p27-fig01.png",
                     bytes_=900_000, caption="Figure 7 Aggregated by Economic Sectors"),
        paper.Figure(page=19, index=2, width=600, height=600, path="figures/p19-fig02.png",
                     bytes_=40_000, caption=""),
    ]
    numbers = [
        {"kind": "percent", "value": "80%", "page": 2, "context": "Eloundou et al. (2023) estimate that GPTs could affect up to 80%"},
        {"kind": "percent", "value": "19%", "page": 3, "context": "support productivity of 19%"},
        {"kind": "percent", "value": "-13.85%", "page": 36, "context": "cognitive gap for undergraduates"},
        {"kind": "sample", "value": "N = 1,024", "page": 14, "context": "recruited N = 1,024 participants"},
        {"kind": "significance", "value": "p<0.001", "page": 36, "context": "cognitive difference p<0.001"},
    ]
    return paper.Digest(path=os.path.join(ROOT, "demo-paper.pdf"),
                        title="Unraveling Generative AI from A Human Intelligence Perspective",
                        authors=["Moore", "Dolansky"], year="2025", pages=39,
                        sections=sections, numbers=numbers, figures=figures,
                        tables=[{"page": 12, "text": "Cognitive | Emotional | Social\n"
                                                      "-13.85 | -13.22 | -0.42\n"
                                                      "1.02 | 3.23 | 1.00\n"
                                                      "37.86 | 61.75 | 64.52"}],
                        warnings=[])


# --------------------------------------------------------------------------- #
# digest
# --------------------------------------------------------------------------- #


def test_digest_markdown_carries_provenance():
    text = make_digest().to_markdown()
    assert "Unraveling Generative AI" in text
    assert "## 章节与节选" in text
    assert "p36" in text or "第 36" in text or "| 36 |" in text
    assert "候选配图" in text
    assert "候选表格" in text


def test_best_figures_prefers_a_captioned_framework_over_a_heatmap():
    ranked = make_digest().best_figures(2)
    assert ranked[0].caption.startswith("Figure 1 Proposed Framework")
    assert "Figure 7" in ranked[1].caption


def test_usable_table_rejects_prose_and_accepts_a_numeric_grid():
    prose = {"page": 1, "text": "we find that the effect  is strong\n"
                                "and the mechanism  is different\n"
                                "therefore the result  is robust"}
    assert author._usable_table(prose) is None
    grid = {"page": 12, "text": "Cognitive | Emotional | Social\n"
                                "-13.85 | -13.22 | -0.42\n"
                                "1.02 | 3.23 | 1.00"}
    rows = author._usable_table(grid)
    assert rows and len(rows) == 3 and rows[0][0] == "Cognitive"


def test_clean_never_cuts_mid_word():
    source = ("The field of generative AI, especially LLMs, has seen "
              "incredible advancements recently with the ability to interact")
    out = author._clean(source, 40)
    assert out.endswith("…")
    assert not out.startswith(" ") and "  " not in out
    cut = out[:-1].strip()
    assert not source.startswith(cut + "xin"), "must not break inside a word"
    assert author._clean("短文本", 40) == "短文本"


def test_title_by_font_reads_the_largest_type():
    class FakePage:
        def extract_text(self, visitor_text=None):
            if visitor_text is None:
                return ""
            for size, text in ((8.5, "Submitted to Information Systems Research\n"),
                               (18.0, "Unraveling Generative AI from A Human\n"),
                               (18.0, "Intelligence Perspective: A Battery of Experiments\n"),
                               (9.0, "Abstract\n")):
                visitor_text(text, None, None, None, size)
            return ""

    assert "Unraveling Generative AI" in paper.title_by_font(FakePage())
    assert "Submitted" not in paper.title_by_font(FakePage())


def test_guess_title_skips_stamps_and_headings():
    page = ("Submitted to Information Systems Research\n"
            "Abstract\n"
            "How Recommendation Affects Customer Search: A Field Experiment\n"
            "Yuan, Chen, Wang and Sun\n")
    assert paper.guess_title(page).startswith("How Recommendation")


# --------------------------------------------------------------------------- #
# skeleton deck
# --------------------------------------------------------------------------- #


def test_skeleton_deck_is_valid_and_placeholder_free():
    deck = spec.Deck.from_dict(author.skeleton_deck(make_digest()))
    assert len(deck.pages) >= 6
    assert deck.pages[0].layout == "cover"
    assert deck.pages[-1].layout == "closing"
    assert spec.validate(deck, schema.field_table()) == []

    text = deck.to_dict()
    blob = str(text)
    for marker in ("TODO", "占位", "示例文字", "lorem"):
        assert marker not in blob


def test_skeleton_deck_keeps_the_peak_ratio_in_range():
    deck = spec.Deck.from_dict(author.skeleton_deck(make_digest()))
    heroes = sum(1 for page in deck.pages if spec.is_hero(page))
    assert 0 < heroes / len(deck.pages) <= 0.45


def test_skeleton_deck_carries_real_numbers_and_a_figure():
    deck = spec.Deck.from_dict(author.skeleton_deck(make_digest(), max_figures=1))
    layouts = deck.layouts()
    assert "image_evidence" in layouts
    figure_pages = [p for p in deck.pages if p.layout == "image_evidence"]
    assert len(figure_pages) == 1
    assert figure_pages[0].data["image"]["path"].endswith(".png")

    chart_pages = [p for p in deck.pages if p.layout == "chart_insight"]
    if chart_pages:
        values = chart_pages[0].data["chart"]["series"][0]["values"]
        assert all(isinstance(v, (int, float)) for v in values)
        assert values, "chart must plot extracted numbers"


def test_skeleton_deck_respects_the_figure_budget():
    deck = spec.Deck.from_dict(author.skeleton_deck(make_digest(), max_figures=9))
    assert deck.layouts().count("image_evidence") <= author.MAX_FIGURE_PAGES


def test_skeleton_deck_without_figures_still_valid():
    digest = make_digest()
    digest.figures = []
    deck = spec.Deck.from_dict(author.skeleton_deck(digest))
    assert "image_evidence" not in deck.layouts()
    assert spec.validate(deck, schema.field_table()) == []


def test_every_layout_used_by_the_skeleton_exists_in_the_schema():
    deck = spec.Deck.from_dict(author.skeleton_deck(make_digest()))
    for name in deck.layouts():
        assert name in schema.LAYOUTS


def test_extract_reports_a_missing_pdf_clearly():
    try:
        paper.extract(os.path.join(ROOT, "definitely-not-here.pdf"))
    except FileNotFoundError as exc:
        assert "definitely-not-here" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("expected FileNotFoundError")


def test_digest_for_deck_is_json_friendly():
    import json

    payload = paper.digest_for_deck(make_digest())
    json.dumps(payload, ensure_ascii=False)
    assert payload["max_deck_pages"] >= 8
    assert payload["figures"] and payload["figures"][0]["path"].endswith(".png")


# --------------------------------------------------------------------------- #
# quality filters (the defects the real-paper run exposed)
# --------------------------------------------------------------------------- #


def test_number_scoring_prefers_results_over_citations():
    sections = [paper.Section("related", "2. Related Work", 1, ""),
                paper.Section("results", "5. Results", 10, "")]
    spans = {1: ["related"], 10: ["results"]}
    citation = paper._score_number("percent", "Chen et al. (2023) report that 80% of jobs change", 1, spans)
    result = paper._score_number("percent", "recommendation PV decreased by 33.4% ***", 10, spans)
    assert result > citation
    assert citation < 2, "a percentage quoted from a citation must not reach the chart"


def test_clean_authors_rejects_mangled_metadata():
    assert paper.clean_authors("2Nev...") == []
    assert paper.clean_authors("Microsoft Word") == []
    assert paper.clean_authors("Yuan, Chen, Wang and Sun") == ["Yuan", "Chen", "Wang", "Sun"]


def test_citation_lines_are_recognised_and_stripped():
    bibliography = (
        "Our results show a strong effect on search behaviour.\n"
        "Customers search more when recommendation rises.\n"
        "Moore S, Dolansky M, Singh M, Palmieri P, Alemi F (2010) The systems thinking scale.\n"
        "Cleveland: Case Western Reserve University.\n"
        "Morgeson FP, Delaney-Klinger K, Hemingway MA (2005) The importance of job autonomy.\n"
        "Agarwal R, Dhar V (2014) Big data, data science, and analytics.\n")
    kept = paper.strip_bibliography(bibliography)
    assert "Our results show" in kept
    assert "Moore S" not in kept
    assert paper.is_citation_line("Moore S, Dolansky M (2010) The systems thinking scale.")
    assert not paper.is_citation_line("Customers search more in product categories.")


def test_section_bullets_drop_fragments_and_citations():
    section = paper.Section("results", "5. Results", 36,
                            "1 tests the hypotheses. "
                            "and the effect is large. "
                            "Moore S, Dolansky M (2010) The systems thinking scale. "
                            "Recommendation raises search by 13% in complementary categories. ")
    bullets = section.bullets()
    assert len(bullets) == 1
    assert bullets[0].startswith("Recommendation raises search")


def test_chart_labels_are_short_and_readable():
    label = author._chart_label("Customers only increase their searches (10% increase) in product", "10%")
    assert 3 <= len(label) <= 17
    assert "(" not in label and ")" not in label.split(" ")[0]


def test_number_sentence_uses_a_real_extracted_number():
    sentence = author._number_sentence([{"value": "13%", "page": 25, "context": "search increases"}])
    assert "13%" in sentence and "p25" in sentence


def test_build_messages_mentions_figure_budget():
    messages = author.build_messages(make_digest(), max_figures=1)
    assert messages[0]["role"] == "system"
    assert "image_evidence" in messages[0]["content"]
    assert "最多 1 页" in messages[0]["content"]
    assert "Unraveling" in messages[1]["content"]


if __name__ == "__main__":  # pragma: no cover - manual runner
    failures = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"ok   {name}")
            except Exception as exc:  # noqa: BLE001
                failures += 1
                print(f"FAIL {name}: {exc}")
    print(f"{failures} failure(s)")
    sys.exit(1 if failures else 0)
