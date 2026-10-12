# -*- coding: utf-8 -*-
"""Tests for the offline repair pass (``deepocean normalize``).

These protect the two mistakes that actually bit us: normalising a *valid* KPI
tone away, and padding/truncating the wrong side of a table row.
"""

from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from deepocean import repair, spec  # noqa: E402


def make_deck() -> spec.Deck:
    return spec.Deck.from_dict({
        "meta": {"title": "t"},
        "pages": [
            {"layout": "cover", "title": "封面"},
            {"layout": "chart_insight", "title": "结果",
             "data": {"chart": {"categories": ["a", "b", "c"],
                                "series": [{"name": "s", "values": [1, 2]}]},
                      "kpis": [{"value": "1", "label": "x", "tone": "up"},
                               {"value": "2", "label": "y", "tone": "flat"}]}},
            {"layout": "key_findings", "title": "发现",
             "data": {"banner": {"heading": "h",
                                 "figures": [{"value": "1", "label": "a", "tone": "down"}]},
                      "cards": [{"title": "c", "body": "b"}]}},
            {"layout": "data_table", "title": "表",
             "data": {"columns": ["A", "B", "C"], "rows": [["1", "2"], ["3", "4", "5", "6"]]}},
        ],
    })


def test_chart_series_are_padded_to_the_category_count():
    result = repair.normalize(make_deck())
    chart = result.deck["pages"][1]["data"]["chart"]
    assert chart["series"][0]["values"] == [1, 2, 0]
    assert any("series[1]" in change.what for change in result.changes)


def test_kpi_and_banner_tones_survive_normalisation():
    """``up``/``down``/``flat`` are data semantics — never rewritten to plain."""
    result = repair.normalize(make_deck())
    kpis = result.deck["pages"][1]["data"]["kpis"]
    assert [k["tone"] for k in kpis] == ["up", "flat"]
    figures = result.deck["pages"][2]["data"]["banner"]["figures"]
    assert figures[0]["tone"] == "down"
    assert not any("语气" in change.what for change in result.changes)


def test_unknown_tone_is_mapped_to_a_real_one():
    deck = make_deck()
    deck.pages[2].data["cards"][0]["tone"] = "warning-red"
    result = repair.normalize(deck)
    assert result.deck["pages"][2]["data"]["cards"][0]["tone"] == "danger"


def test_table_rows_are_made_exactly_as_wide_as_the_header():
    result = repair.normalize(make_deck())
    rows = result.deck["pages"][3]["data"]["rows"]
    assert rows == [["1", "2", ""], ["3", "4", "5"]]
    table_changes = [c for c in result.changes if c.layout == "data_table"]
    assert len(table_changes) == 2


def test_clean_deck_is_left_alone():
    deck = make_deck()
    first = repair.normalize(deck)
    again = repair.normalize(spec.Deck.from_dict(first.deck))
    assert again.changes == []


def test_hero_ratio_is_pulled_back_into_the_band():
    # 8 pages: cover + key_findings + closing are hero by layout (3/8 = 37.5%),
    # so two explicit "hero: true" flags push it over 45% and must be dropped.
    pages = [{"layout": "cover", "title": "1"}]
    pages += [{"layout": "two_column", "title": str(i)} for i in range(2, 5)]
    pages += [{"layout": "chart_insight", "title": "5", "hero": True},
              {"layout": "big_number", "title": "6", "hero": True},
              {"layout": "key_findings", "title": "7"},
              {"layout": "closing", "title": "8"}]
    result = repair.normalize(spec.Deck.from_dict({"meta": {"title": "t"}, "pages": pages}))
    heroes = sum(1 for page in result.deck["pages"]
                 if page.get("hero") or page.get("layout") in ("cover", "key_findings", "closing"))
    assert heroes / len(result.deck["pages"]) <= 0.45
    assert any("hero" in change.what for change in result.changes)


def test_normalize_writes_a_loadable_file(tmp_path=None):
    import json
    import tempfile

    deck = make_deck()
    directory = tempfile.mkdtemp()
    path = os.path.join(directory, "deck.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(deck.to_dict(), fh, ensure_ascii=False)

    result = repair.normalize_file(path)
    assert result.touched
    reloaded = spec.Deck.load(path)
    assert reloaded.pages[1].data["chart"]["series"][0]["values"] == [1, 2, 0]


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
    raise SystemExit(1 if failures else 0)
