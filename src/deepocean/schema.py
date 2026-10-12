# -*- coding: utf-8 -*-
"""The page layout contract — shared by the PPTX renderer and the HTML renderer.

This module is the **interface** between a deck document and the things that
draw it.  Two independent renderers implement the same twelve layouts:

* :mod:`deepocean.layouts`  -> real PowerPoint geometry (python-pptx)
* :mod:`deepocean.html`     -> pixel-identical HTML/CSS preview

Because both read the field table below, a deck can never render in the HTML
preview but break in PowerPoint.

Adding a layout
---------------
1. add an entry to :data:`LAYOUTS` (fields, chrome, hero flag),
2. implement ``render_<layout>(slide, page, ctx)`` in ``layouts.py``,
3. implement the matching branch in ``html.py``,
4. add the page to ``examples/demo-deck.yaml``.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

#: Tone vocabulary shared by every component: how a block is emphasised.
TONES = ("plain", "tint", "primary", "accent", "neutral", "danger", "alert")

#: Field types used in the tables below (documentation, not runtime enforced).
TYPES = ("str", "int", "float", "bool", "list", "dict", "list[str]", "list[dict]")


def _f(type_: str, required: bool = False, note: str = "", default: Any = None) -> Dict[str, Any]:
    return {"type": type_, "required": required, "note": note, "default": default}


LAYOUTS: Dict[str, Dict[str, Any]] = {
    # ------------------------------------------------------------------ 01
    "cover": {
        "zh": "封面",
        "en": "Cover",
        "hero": True,
        "chrome": False,          # draws its own top bar, skips title block + footer
        "asymmetric": True,
        "fields": {
            "english_title": _f("str", note="封面英文副标，验证学术出处"),
            "authors": _f("str", note="汇报人 / 作者行"),
            "affiliation": _f("str", note="单位 · 方向 · 日期"),
            "series": _f("str", note="右上角刊名角标，如 ISR · 2025"),
            "note": _f("str", note="底部信息条，如 样本 555,800 · 26 个品类"),
            "band": _f("str", note="底部色带文字", default=""),
        },
    },
    # ------------------------------------------------------------------ 02
    "two_column": {
        "zh": "非对称双栏",
        "en": "Asymmetric two-column",
        "hero": False,
        "chrome": True,
        "asymmetric": True,
        "fields": {
            "ratio": _f("float", note="左栏宽度占比，默认 0.60（0.5–0.7）", default=0.60),
            "left": _f("dict", True, "左主卡 {title, body, items[], footer, tone}"),
            "right": _f("list", True, "右侧卡片列 [{title, body, items[], tone, chip, footer}]"),
        },
    },
    # ------------------------------------------------------------------ 03
    "big_number": {
        "zh": "巨型数字 + 洞察",
        "en": "Big number + insight",
        "hero": False,
        "chrome": True,
        "asymmetric": True,
        "fields": {
            "mode": _f("str", note="hero = 1 大 + 2 小；grid = 并排 2–4 张", default="hero"),
            "items": _f("list", True, "[{number, unit, title, body, tone}]，2–4 项"),
        },
    },
    # ------------------------------------------------------------------ 04
    "experiment_design": {
        "zh": "实验设计（流程 + 对比）",
        "en": "Experiment design",
        "hero": False,
        "chrome": True,
        "asymmetric": True,
        "fields": {
            "steps": _f("list", True, "[{label, text}]，2–3 步流程"),
            "groups": _f("dict", True, "left / right 对比组 {title, body, items[], tone}"),
            "vs": _f("str", note="中间对比标记，默认 VS", default="VS"),
            "verdict": _f("str", note="对比区下方一句话结论"),
        },
    },
    # ------------------------------------------------------------------ 05
    "roadmap": {
        "zh": "左标题栏 + 右步骤",
        "en": "Roadmap",
        "hero": False,
        "chrome": True,
        "asymmetric": True,
        "fields": {
            "aside": _f("dict", True, "左深蓝栏 {title, body, items[], footer}"),
            "steps": _f("list", True, "[{no, title, body, meta}]，2–4 步"),
        },
    },
    # ------------------------------------------------------------------ 06 / 10
    "chart_insight": {
        "zh": "左图表 + 右洞察",
        "en": "Chart + insight",
        "hero": False,
        "chrome": True,
        "asymmetric": True,
        "fields": {
            "chart": _f("dict", True,
                        "{type: bar|line|doughnut, categories[], series[{name, values[], color}], "
                        "title, unit, height, note}"),
            "side_ratio": _f("float", note="图表卡宽度占比，默认 0.60", default=0.60),
            "kpis": _f("list", note="右侧 KPI [{value, label, note, tone}]"),
            "cards": _f("list", note="右侧解读卡 [{title, body, tone}]"),
            "takeaway": _f("dict", note="深蓝结论卡 {label, text}"),
        },
    },
    # ------------------------------------------------------------------ 07
    "split_cards": {
        "zh": "双栏对比卡",
        "en": "Split comparison cards",
        "hero": False,
        "chrome": True,
        "asymmetric": True,
        "fields": {
            "left": _f("dict", True, "{chip, chip_en, title, body, items[], footer, tone}"),
            "right": _f("dict", True, "{chip, chip_en, title, body, items[], footer, tone}"),
            "ratio": _f("float", note="左卡宽度占比，默认 0.56", default=0.56),
        },
    },
    # ------------------------------------------------------------------ 08
    "concept_flow": {
        "zh": "概念框架（左 → 中 → 右）",
        "en": "Conceptual framework",
        "hero": False,
        "chrome": True,
        "asymmetric": True,
        "fields": {
            "left": _f("dict", True, "{title, body, items[]}"),
            "center": _f("dict", True, "{label, note}"),
            "right": _f("dict", True, "{title, body, items[]}"),
            "takeaway": _f("str", note="底部一句话"),
        },
    },
    # ------------------------------------------------------------------ 09
    "matrix2x2": {
        "zh": "2×2 机制矩阵",
        "en": "2x2 matrix",
        "hero": False,
        "chrome": True,
        "asymmetric": True,
        "fields": {
            "aside": _f("dict", True, "{title, body, items[], axes:{x, y}}"),
            "quadrants": _f("list", True,
                            "4 项 [{no, title, condition, result, note, tone}]，顺序：LT RT LB RB"),
            "center_label": _f("str", note="中心锚点文字"),
        },
    },
    # ------------------------------------------------------------------ extra
    "data_table": {
        "zh": "数据表",
        "en": "Data table",
        "hero": False,
        "chrome": True,
        "asymmetric": False,
        "fields": {
            "columns": _f("list[str]", True, "表头文字"),
            "rows": _f("list", True, "单元格文字，行数不限（<=8 行最佳）"),
            "caption": _f("str", note="表号 / 来源"),
            "highlight_col": _f("int", note="高亮列索引（0 起）", default=-1),
            "first_col_bold": _f("bool", note="首列加粗", default=True),
        },
    },
    # ------------------------------------------------------------------ 11
    "key_findings": {
        "zh": "核心结论横幅 + 启示",
        "en": "Key findings banner",
        "hero": True,
        "chrome": True,
        "asymmetric": True,
        "fields": {
            "banner": _f("dict", True, "{heading, figures:[{value, unit, label, tone}]}"),
            "cards": _f("list", True, "[{title, body, tone}]，2–3 张"),
            "cards_ratio": _f("float", note="首卡宽度占比，默认 0.46", default=0.46),
        },
    },
    # ------------------------------------------------------------------ 12
    "closing": {
        "zh": "总结与展望",
        "en": "Closing",
        "hero": True,
        "chrome": False,
        "asymmetric": True,
        "fields": {
            "quote": _f("dict", True, "{text, source}"),
            "panels": _f("list", True, "[{title, body, tone}]，2 张"),
            "thanks": _f("str", note="致谢条文字"),
        },
    },
}

#: Every layout name, in guide order (the 12-page reference deck uses 11 of them).
LAYOUT_NAMES: List[str] = list(LAYOUTS)

#: Short aliases so hand-written decks stay readable.
ALIASES = {
    "intro": "cover",
    "title": "cover",
    "two-col": "two_column",
    "2col": "two_column",
    "chart": "chart_insight",
    "table": "data_table",
    "matrix": "matrix2x2",
    "flow": "concept_flow",
    "end": "closing",
    "thanks": "closing",
}


def resolve(name: str) -> str:
    """Map an alias to its canonical layout name."""
    key = (name or "").strip().lower().replace(" ", "_")
    key = ALIASES.get(key, key)
    if key not in LAYOUTS:
        raise KeyError(f"unknown layout {name!r}; choose one of {', '.join(LAYOUT_NAMES)}")
    return key


def fields_of(layout: str) -> Dict[str, Dict[str, Any]]:
    return LAYOUTS[resolve(layout)]["fields"]


def is_hero(layout: str) -> bool:
    return bool(LAYOUTS[resolve(layout)]["hero"])


def needs_chrome(layout: str) -> bool:
    """True when the shared top bar + title block + footer must be drawn."""
    return bool(LAYOUTS[resolve(layout)]["chrome"])


def field_table() -> Dict[str, Dict[str, Dict[str, Any]]]:
    """``{layout: {field: spec}}`` — the shape :func:`spec.validate` wants."""
    return {name: cfg["fields"] for name, cfg in LAYOUTS.items()}


def describe(layout: Optional[str] = None) -> str:
    """Markdown reference for one layout or the whole library."""
    names = [resolve(layout)] if layout else LAYOUT_NAMES
    lines: List[str] = []
    for name in names:
        cfg = LAYOUTS[name]
        lines.append(f"### `{name}` — {cfg['zh']} / {cfg['en']}")
        lines.append("")
        lines.append(f"- hero page: {'yes' if cfg['hero'] else 'no'} · "
                     f"shared chrome: {'yes' if cfg['chrome'] else 'no (draws its own)'} · "
                     f"asymmetric: {'yes' if cfg['asymmetric'] else 'no'}")
        lines.append("")
        lines.append("| field | type | required | note |")
        lines.append("|---|---|---|---|")
        for fname, spec in cfg["fields"].items():
            lines.append(f"| `{fname}` | {spec['type']} | {'yes' if spec['required'] else 'no'} | {spec['note']} |")
        lines.append("")
    return "\n".join(lines)
