# -*- coding: utf-8 -*-
"""The deck specification model: loading, round-tripping and validating."""

from __future__ import annotations

import json
import os
import shutil
import tempfile

try:  # pytest is a dev dependency; the fallback keeps this file runnable alone
    import pytest
except ImportError:  # pragma: no cover - exercised only in stripped environments
    pytest = None  # type: ignore

from deepocean import schema, spec, tokens

DECK_DICT = {
    "meta": {
        "title": "推荐如何影响消费者搜索",
        "subtitle": "How Recommendation Affects Customer Search",
        "kicker": "组会文献汇报",
        "journal": "ISR · 2025",
        "authors": ["Yuan", "Chen", "Wang", "Sun"],
        "source_note": "组会文献汇报 · ISR 2025, 36(1): 84-106",
    },
    "pages": [
        {"layout": "cover", "title": "推荐如何影响消费者搜索",
         "data": {"authors": "汇报人 · 李明", "affiliation": "管理科学与工程 · 2026"}},
        {"layout": "two_column", "kicker": "01 · BACKGROUND", "title": "研究背景",
         "data": {"left": {"title": "现象", "body": "推荐位改变了搜索路径"},
                  "right": [{"title": "缺口", "body": "既有文献忽略品类异质性"}]}},
        {"layout": "chart_insight", "title": "主效应",
         "data": {"chart": {"type": "bar", "categories": ["A", "B"],
                            "series": [{"name": "搜索量", "values": [1, 2]}],
                            "height": 300}}},
    ],
}


class _Raises:
    """Minimal ``pytest.raises`` stand-in for the manual runner."""

    def __init__(self, expected: type) -> None:
        self.expected = expected
        self.value: BaseException = Exception()

    def __enter__(self) -> "_Raises":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        if exc_type is None:
            raise AssertionError(f"expected {self.expected.__name__} to be raised")
        if not issubclass(exc_type, self.expected):
            return False
        self.value = exc
        return True


def _raises(expected: type) -> "_Raises":
    return _Raises(expected)


class _TmpDir:
    """``pytest``-style temporary directory usable by the manual runner too."""

    def __init__(self) -> None:
        self._path = ""

    def __enter__(self) -> "_TmpDir":
        self._path = tempfile.mkdtemp(prefix="deepocean-test-")
        return self

    def __exit__(self, *exc: object) -> bool:
        shutil.rmtree(self._path, ignore_errors=True)
        return False

    def __str__(self) -> str:
        return self._path

    def __fspath__(self) -> str:
        return self._path


def _deck() -> spec.Deck:
    return spec.Deck.from_dict(json.loads(json.dumps(DECK_DICT)))


# --------------------------------------------------------------------------- #
# Construction & fallbacks
# --------------------------------------------------------------------------- #


def test_deck_from_dict_reads_meta_and_pages():
    deck = _deck()
    assert len(deck) == 3
    assert deck.meta.title == "推荐如何影响消费者搜索"
    assert deck.meta.authors == ["Yuan", "Chen", "Wang", "Sun"]
    assert deck.layouts() == ["cover", "two_column", "chart_insight"]
    assert [p.layout for p in deck] == deck.layouts()


def test_page_field_fallbacks():
    page = spec.Page.from_dict({"layout": "two_column"})
    assert page.title == ""
    assert page.title_en == ""
    assert page.kicker == ""
    assert page.subtitle == ""
    assert page.hero is None
    assert page.data == {}
    assert page.get("title", "fallback") == ""          # attribute wins over default
    assert page.get("nonexistent", "fallback") == "fallback"

    # a page without a layout falls back to the default content layout
    blank = spec.Page.from_dict({})
    assert blank.layout == "two_column"
    assert blank.get("ratio", 0.6) == 0.6


def test_page_treats_unknown_top_level_keys_as_layout_data():
    page = spec.Page.from_dict({"layout": "data_table", "columns": ["a"], "rows": [["b"]]})
    assert page.data["columns"] == ["a"]
    assert page.data["rows"] == [["b"]]


def test_page_id_and_notes_are_preserved():
    page = spec.Page.from_dict({"layout": "cover", "id": "p01", "notes": "开场停顿"})
    assert page.data["id"] == "p01"
    assert page.data["notes"] == "开场停顿"
    assert "id" not in page.to_dict()


def test_meta_defaults_and_string_authors():
    meta = spec.DeckMeta.from_dict(None)
    assert meta.title == "Untitled deck"
    assert meta.kicker == "组会文献汇报"
    assert meta.authors == []
    assert meta.language == "zh"
    assert spec.DeckMeta.from_dict({"authors": "李明"}).authors == ["李明"]
    # to_dict drops empty-but-set values, but title/kicker/language always land
    assert spec.DeckMeta.from_dict({"language": "en"}).to_dict() == {
        "title": "Untitled deck", "kicker": "组会文献汇报", "language": "en"}
    assert spec.DeckMeta.from_dict({"title": "t", "subtitle": ""}).to_dict() == {
        "title": "t", "kicker": "组会文献汇报", "language": "zh"}
    assert spec.DeckMeta.from_dict({"journal": "ISR"}).to_dict()["journal"] == "ISR"
    assert "authors" not in spec.DeckMeta.from_dict({"title": "t"}).to_dict() or \
        spec.DeckMeta.from_dict({"title": "t"}).to_dict()["authors"] == []


def test_deck_requires_pages():
    for broken in ({}, {"pages": []}, {"meta": {"title": "x"}, "pages": None}):
        with _raises(spec.SpecError):
            spec.Deck.from_dict(broken)
    with _raises(spec.SpecError):
        spec.Deck.from_dict(["not", "a", "mapping"])
    with _raises(spec.SpecError):
        spec.Deck.from_dict({"pages": {"layout": "cover"}})


def test_page_from_dict_rejects_non_mapping():
    with _raises(spec.SpecError):
        spec.Page.from_dict("cover")


def test_page_need_raises_for_empty_values():
    page = spec.Page.from_dict({"layout": "chart_insight", "data": {"chart": {}}})
    with _raises(spec.SpecError):
        page.need("chart")
    page.data["chart"] = {"type": "bar"}
    assert page.need("chart")["type"] == "bar"


# --------------------------------------------------------------------------- #
# Serialisation
# --------------------------------------------------------------------------- #


def test_json_round_trip():
    deck = _deck()
    payload = deck.to_dict()
    again = spec.Deck.from_dict(json.loads(json.dumps(payload, ensure_ascii=False)))

    assert again.to_dict() == payload
    assert again.meta.source_note == deck.meta.source_note
    assert again.pages[1].data["left"]["title"] == "现象"
    assert again.pages[1].kicker == "01 · BACKGROUND"
    # round trip twice for stability
    assert spec.Deck.from_dict(again.to_dict()).to_dict() == payload


def test_to_dict_omits_empty_optional_page_keys():
    page = spec.Page.from_dict({"layout": "cover"})
    assert page.to_dict() == {"layout": "cover"}
    page.title = "T"
    assert page.to_dict() == {"layout": "cover", "title": "T"}


def test_json_file_round_trip():
    with _TmpDir() as tmp:
        path = os.path.join(str(tmp), "deck.json")
        deck = _deck()
        saved = deck.save(path)
        assert os.path.isfile(saved)
        loaded = spec.Deck.load(path)
        assert loaded.to_dict() == deck.to_dict()
        assert loaded.source_path == os.path.abspath(path)
        with open(path, encoding="utf-8") as handle:
            assert spec.loads(handle.read(), fmt="json").to_dict() == deck.to_dict()


def test_loads_auto_detects_json():
    text = json.dumps(DECK_DICT, ensure_ascii=False)
    assert spec.loads(text).meta.journal == "ISR · 2025"


def test_deck_helpers():
    deck = _deck()
    deck.meta.footer_note = ""
    assert deck.resolved_footer_note() == "组会文献汇报 · 推荐如何影响消费者搜索 · ISR · 2025"
    deck.meta.footer_note = "自定义页脚"
    assert deck.resolved_footer_note() == "自定义页脚"
    assert deck.hero_count() == 1          # only cover is in tokens.HERO_LAYOUTS
    assert spec.is_hero(deck.pages[0]) is True
    assert spec.is_hero(deck.pages[1]) is False
    assert spec.is_hero(deck.pages[2]) is False      # chart_insight: chrome hero, not a peak page
    # an explicit page flag always wins over the layout defaults
    deck.pages[1].hero = True
    assert deck.hero_count() == 2


# --------------------------------------------------------------------------- #
# YAML (optional dependency)
# --------------------------------------------------------------------------- #

YAML_TEXT = """
meta:
  title: 组会汇报
pages:
  - layout: cover
    title: 封面
  - layout: two_column
    title: 背景
    data:
      left: {title: A, body: B}
      right: [{title: C}]
"""


def _has_yaml() -> bool:
    try:
        import yaml  # noqa: F401
    except ImportError:
        return False
    return True


def test_yaml_load_works_or_raises_a_helpful_spec_error():
    if not _has_yaml():
        with _raises(spec.SpecError) as excinfo:
            spec.loads(YAML_TEXT, fmt="yaml")
        message = str(excinfo.value)
        assert "PyYAML" in message
        assert "pip install" in message
        assert "JSON" in message
    else:
        deck = spec.loads(YAML_TEXT, fmt="yaml")
        assert len(deck) == 2
        assert deck.meta.title == "组会汇报"
        assert spec.dumps_yaml({"a": 1}).strip() in ("a: 1", '{"a": 1}')


def test_yaml_save_falls_back_to_json_without_pyyaml():
    with _TmpDir() as tmp:
        path = os.path.join(str(tmp), "deck.yaml")
        spec.Deck.from_dict(DECK_DICT).save(path)
        with open(path, encoding="utf-8") as handle:
            text = handle.read()
        if not _has_yaml():
            json.loads(text)                   # the fallback must stay valid JSON
        else:
            assert "pages:" in text


# --------------------------------------------------------------------------- #
# Validation
# --------------------------------------------------------------------------- #


def test_validate_accepts_a_well_formed_deck():
    assert spec.validate(_deck(), schema.field_table()) == []


def test_validate_catches_unknown_layout():
    deck = _deck()
    deck.pages.append(spec.Page.from_dict({"layout": "mystery", "title": "x"}))
    problems = spec.validate(deck, schema.field_table())
    assert any("unknown layout" in p and "mystery" in p for p in problems), problems


def test_validate_catches_missing_required_field():
    deck = spec.Deck.from_dict({
        "meta": {"title": "t"},
        "pages": [{"layout": "two_column", "title": "只有左栏", "data": {"left": {"title": "A"}}}],
    })
    problems = spec.validate(deck, schema.field_table())
    assert any("missing required field 'right'" in p for p in problems), problems


def test_validate_catches_empty_deck_and_missing_title():
    empty = spec.Deck(meta=spec.DeckMeta(title=""), pages=[])
    problems = spec.validate(empty)
    assert "deck has no pages" in problems
    assert "meta.title is empty" in problems


def test_validate_without_fields_table_still_checks_titles():
    deck = spec.Deck.from_dict({
        "meta": {"title": "t"},
        "pages": [{"layout": "two_column"}, {"layout": "cover"}],
    })
    problems = spec.validate(deck)
    assert len(problems) == 1
    assert "content pages need a title" in problems[0]
    assert "page 01" in problems[0]


# --------------------------------------------------------------------------- #
# Schema table
# --------------------------------------------------------------------------- #


def test_schema_exposes_twelve_layouts_and_a_consistent_field_table():
    assert len(schema.LAYOUTS) >= 12
    table = schema.field_table()
    assert set(table) == set(schema.LAYOUTS)
    for name, cfg in schema.LAYOUTS.items():
        assert cfg["zh"] and cfg["en"]
        assert isinstance(cfg["hero"], bool)
        assert isinstance(cfg["chrome"], bool)
        assert isinstance(cfg["asymmetric"], bool)
        assert table[name] == cfg["fields"]
        for field_name, field_spec in cfg["fields"].items():
            assert field_spec["type"] in schema.TYPES, (name, field_name)
            assert isinstance(field_spec["required"], bool)
            assert "default" in field_spec
        assert schema.resolve(name) == name
        assert schema.fields_of(name) == cfg["fields"]
        assert schema.is_hero(name) == cfg["hero"]
        assert schema.needs_chrome(name) == cfg["chrome"]


def test_schema_resolves_aliases_and_rejects_unknown_names():
    for alias, target in schema.ALIASES.items():
        assert target in schema.LAYOUTS
        assert schema.resolve(alias) == target
    assert schema.resolve("2COL") == "two_column"            # case folded
    assert schema.resolve("Data Table") == "data_table"      # spaces folded
    assert schema.resolve("CHART") == "chart_insight"
    with _raises(KeyError):
        schema.resolve("Two-Column")                         # dashes are not folded
    with _raises(KeyError):
        schema.resolve("mystery")


def test_schema_describe_is_markdown():
    text = schema.describe("cover")
    assert "### `cover`" in text
    assert "| field | type | required | note |" in text
    full = schema.describe()
    for name in schema.LAYOUT_NAMES:
        assert f"### `{name}`" in full


def test_field_table_matches_tokens_hero_layouts():
    for name in tokens.HERO_LAYOUTS:
        assert schema.LAYOUTS[name]["hero"] is True
    assert schema.LAYOUTS["cover"]["chrome"] is False
    assert schema.LAYOUTS["closing"]["chrome"] is False
    assert schema.LAYOUTS["two_column"]["chrome"] is True


def test_describe_fields_markdown_columns():
    text = spec.describe_fields(schema.field_table())
    lines = text.splitlines()
    assert lines[0] == "| layout | field | type | required | note |"
    assert "---" in lines[1]
    for line in lines[2:]:
        cells = [c.strip() for c in line.strip("|").split("|")]
        # the note column legitimately contains ``|`` (e.g. "bar|line"), so only
        # the four leading columns are positionally checkable
        assert cells[0].startswith("`") and cells[0].endswith("`"), line
        assert cells[1].startswith("`") and cells[1].endswith("`"), line
        assert cells[2] in schema.TYPES, line
        assert cells[3] in ("yes", "no"), line


if __name__ == "__main__":  # pragma: no cover - manual runner fallback
    passed = 0
    for name, fn in sorted(list(globals().items())):
        if name.startswith("test_") and callable(fn):
            fn()
            passed += 1
    print(f"test_spec: {passed} tests passed (manual runner, pytest not required)")


if pytest is None:  # pragma: no cover - keeps linters quiet about the import
    pass
