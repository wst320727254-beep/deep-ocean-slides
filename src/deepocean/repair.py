# -*- coding: utf-8 -*-
"""Deck repair — offline, deterministic fixes for structural slips.

Anyone (or any agent) hand-writing a ``deck.yaml`` makes the same small
mistakes: a chart whose ``series`` is one value short, a table row with a cell
too few, a ``tone`` that is not in the vocabulary.  None of those need a model
to fix, so :func:`normalize` repairs them and **reports what it touched** —
never inventing content, only trimming or padding structure.

    deepocean normalize deck.yaml            # 写回并打印改动
    deepocean normalize deck.yaml --out fixed.yaml
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from . import schema, spec, tokens


@dataclass
class Change:
    """One structural repair, with the page it happened on."""

    page: int
    layout: str
    what: str
    detail: str = ""

    def __str__(self) -> str:
        return f"p{self.page} [{self.layout}] {self.what}" + (f"：{self.detail}" if self.detail else "")


@dataclass
class RepairResult:
    deck: Dict[str, Any]
    changes: List[Change] = field(default_factory=list)

    @property
    def touched(self) -> bool:
        return bool(self.changes)


#: Every ``tone`` a renderer understands.  Card tones come from
#: :data:`schema.TONES`; KPI / banner / big-number tones carry data semantics
#: (``up`` teal, ``down`` brick, ``flat`` navy) and must NOT be normalised away.
_TONES = set(schema.TONES) | {"up", "down", "flat", "positive", "negative", "neutral_number"}

#: Aliases collapsed onto a canonical tone when the value is unknown.
_TONE_ALIASES = (
    ("up", "up"), ("increase", "up"), ("positive", "up"), ("good", "up"),
    ("down", "down"), ("decrease", "down"), ("negative", "down"), ("bad", "down"),
    ("flat", "flat"), ("neutral_number", "flat"), ("same", "flat"),
    ("danger", "danger"), ("warn", "danger"), ("red", "danger"),
    ("primary", "primary"), ("dark", "primary"), ("navy", "primary"),
    ("accent", "accent"), ("mint", "accent"), ("teal", "accent"),
    ("grey", "tint"), ("gray", "tint"), ("light", "tint"),
)


def _as_list(value: Any) -> List[Any]:
    if value is None:
        return []
    return list(value) if isinstance(value, (list, tuple)) else [value]


def _fix_chart(page: Dict[str, Any], changes: List[Change], index: int) -> None:
    """Align ``series[*].values`` with ``categories`` (the classic off-by-one)."""
    chart = page.get("data", {}).get("chart")
    if not isinstance(chart, dict):
        return
    categories = _as_list(chart.get("categories"))
    if not categories:
        return
    series = [s for s in _as_list(chart.get("series")) if isinstance(s, dict)]
    chart["series"] = series
    for position, item in enumerate(series, 1):
        values = _as_list(item.get("values"))
        if len(values) == len(categories):
            continue
        if len(values) < len(categories):
            values = values + [0] * (len(categories) - len(values))
            changes.append(Change(index, "chart_insight",
                                  f"series[{position}] 数值不足，补 0 对齐类目",
                                  f"{len(values) - (len(categories) - len(values))} → {len(categories)}"))
        else:
            dropped = values[len(categories):]
            values = values[:len(categories)]
            changes.append(Change(index, "chart_insight",
                                  f"series[{position}] 数值多出，截断到类目数",
                                  f"丢弃 {dropped}"))
        item["values"] = values


def _fix_table(page: Dict[str, Any], changes: List[Change], index: int) -> None:
    """Make every row exactly as wide as the header."""
    data = page.get("data", {})
    columns = _as_list(data.get("columns"))
    rows = [row for row in _as_list(data.get("rows"))]
    if not columns or not rows:
        return
    width = len(columns)
    fixed: List[List[str]] = []
    for position, row in enumerate(rows, 1):
        cells = [str(cell) for cell in _as_list(row)]
        if len(cells) == width:
            fixed.append(cells)
            continue
        if len(cells) < width:
            fixed.append(cells + [""] * (width - len(cells)))
            changes.append(Change(index, "data_table",
                                  f"rows[{position}] 补空单元格", f"{len(cells)} → {width}"))
        else:
            fixed.append(cells[:width])
            changes.append(Change(index, "data_table",
                                  f"rows[{position}] 截断多余单元格", f"{len(cells)} → {width}"))
    data["rows"] = fixed


def _fix_tones(node: Any, changes: List[Change], index: int, layout: str, path: str = "") -> None:
    """Unknown ``tone`` values fall back to ``plain`` instead of failing to render."""
    if isinstance(node, dict):
        tone = node.get("tone")
        if isinstance(tone, str) and tone and tone not in _TONES:
            nearest = _nearest_tone(tone)
            node["tone"] = nearest
            changes.append(Change(index, layout, f"{path or 'tone'} 不是合法语气",
                                  f"{tone!r} → {nearest!r}"))
        for key, value in node.items():
            _fix_tones(value, changes, index, layout, f"{path}.{key}".lstrip("."))
    elif isinstance(node, list):
        for position, item in enumerate(node, 1):
            _fix_tones(item, changes, index, layout, f"{path}[{position}]")


def _nearest_tone(value: str) -> str:
    lowered = value.strip().lower()
    for tone in _TONES:
        if tone in lowered:
            return tone
    for alias, tone in _TONE_ALIASES:
        if alias in lowered:
            return tone
    return "plain"


def _fix_hero_ratio(page_list: List[Dict[str, Any]], changes: List[Change]) -> None:
    """Keep the peak ratio inside 25–45% (R002) by dropping redundant hero flags."""
    def is_hero(page: Dict[str, Any]) -> bool:
        return bool(page.get("hero")) or page.get("layout") in tokens.HERO_LAYOUTS

    explicit = [page for page in page_list if page.get("hero") is True]
    while page_list and explicit:
        ratio = sum(1 for page in page_list if is_hero(page)) / len(page_list)
        if ratio <= 0.45:
            return
        dropped = explicit.pop(0)
        dropped["hero"] = False
        changes.append(Change(page_list.index(dropped) + 1, str(dropped.get("layout")),
                              "取消多余的 hero 标记", "让 Hero 占比回到 25%–45%"))


def normalize(deck: spec.Deck) -> RepairResult:
    """Repair a deck's structure and return the JSON-ready dict plus the changes.

    Only structure is touched: no text is rewritten, no number invented, no page
    added or removed.
    """
    data = deck.to_dict()
    pages = [page for page in (data.get("pages") or []) if isinstance(page, dict)]
    changes: List[Change] = []

    for index, page in enumerate(pages, 1):
        layout = str(page.get("layout") or "")
        if not isinstance(page.get("data"), dict):
            if "data" in page:
                page["data"] = {}
                changes.append(Change(index, layout, "data 不是对象，已重置为空"))
            continue
        if layout == "chart_insight":
            _fix_chart(page, changes, index)
        if layout == "data_table":
            _fix_table(page, changes, index)
        _fix_tones(page.get("data"), changes, index, layout)

    _fix_hero_ratio(pages, changes)
    data["pages"] = pages
    return RepairResult(deck=data, changes=changes)


def normalize_file(path: str, out_path: Optional[str] = None) -> RepairResult:
    """Load, repair, write.  Returns the same :class:`RepairResult`."""
    deck = spec.Deck.load(path)
    result = normalize(deck)
    spec.Deck.from_dict(result.deck).save(out_path or path)
    return result
