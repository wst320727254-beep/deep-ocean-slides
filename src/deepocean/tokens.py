# -*- coding: utf-8 -*-
"""Deep Ocean design tokens — the single source of truth.

Everything in this module is **normative**.  The PPTX generator, the HTML
renderer, the migration helpers and the automatic linter all read from here, so
a deck cannot silently drift away from the style guide.

Coordinate system
-----------------
All lengths are **px on a 1280 x 720 canvas** (16:9), origin at the top-left
corner — exactly the numbers printed in the style guide.  ``pt = px * 0.75``.
Use :mod:`deepocean.units` to convert to inches / cm / EMU for other tools.

Layout contract (four bands, locked for every content page)
-----------------------------------------------------------
===========  ==========================  =================================
Band         Range (px)                  Contents
===========  ==========================  =================================
A top bar    y 0-60                      navy bar, teal square, journal tag
B title      y 72-140                    kicker 14 / title 30 / subtitle 15
C content    y 200-640                   cards, height 430-440, fill >= 80%
D footer     y 680-720                   source note left, page number right
===========  ==========================  =================================
"""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

# --------------------------------------------------------------------------- #
# Identity
# --------------------------------------------------------------------------- #

NAME = "Deep Ocean"
NAME_ZH = "深海学术风"
VERSION = "1.0.0"
TAGLINE_ZH = "像论文，不像海报"
TAGLINE_EN = "Reads like a paper, not a poster."
LICENSE = "MIT"
HOMEPAGE = "https://github.com/wst320727254-beep/deep-ocean-slides"

# --------------------------------------------------------------------------- #
# Canvas & grid
# --------------------------------------------------------------------------- #

CANVAS: Dict[str, object] = {
    "width_px": 1280,
    "height_px": 720,
    "aspect": "16:9",
    "width_in": 13.3333,      # PowerPoint default widescreen
    "height_in": 7.5,
    "width_cm": 33.87,
    "height_cm": 19.05,
    "px_per_inch": 96.0,
}

SAFE_MARGIN_PX = 40          # left/right safe margin -> usable width 1200 px
CARD_GAP_PX = 20             # gutter between cards in a row
CONTENT_WIDTH_PX = CANVAS["width_px"] - 2 * SAFE_MARGIN_PX  # 1200

BANDS: Dict[str, Dict[str, int]] = {
    "top_bar": {"y": 0, "h": 60},
    "title": {"y": 72, "h": 68},       # 72 - 140
    "content": {"y": 200, "h": 440},   # 200 - 640
    "footer": {"y": 680, "h": 40},     # 680 - 720
}

#: Every element must live inside this box (content pages).
SAFE_AREA = {
    "x": SAFE_MARGIN_PX,
    "y": BANDS["top_bar"]["h"],
    "w": CONTENT_WIDTH_PX,
    "h": CANVAS["height_px"] - BANDS["top_bar"]["h"],
}

#: Cover / closing pages may break these bands, nothing else may.
CHROME_EXEMPT_LAYOUTS = ("cover", "closing")

# --------------------------------------------------------------------------- #
# Colour system  (<= 4 brand colours + neutrals)
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class Swatch:
    """One palette entry with the semantics the guide assigns to it."""

    key: str
    name_zh: str
    name_en: str
    hex: str
    use_zh: str
    use_en: str
    role: str = "surface"      # brand | surface | text | semantic
    budget: str = ""

    @property
    def rgb(self) -> Tuple[int, int, int]:
        return (int(self.hex[1:3], 16), int(self.hex[3:5], 16), int(self.hex[5:7], 16))


#: Ordered brand + surface palette.  Keep ``key`` stable: deck specs and the
#: linter both reference these names instead of raw hex values.
PALETTE: "OrderedDict[str, Swatch]" = OrderedDict(
    [
        ("navy", Swatch("navy", "深海蓝 · 主色", "Deep Ocean Navy", "#1B3A5C",
                        "顶条 / 主标题 / 强调数字 / 页码 / 深色卡底",
                        "Top bar, page titles, anchor numbers, page tag, dark cards",
                        role="brand")),
        ("teal", Swatch("teal", "青绿 · 辅色", "Tide Teal", "#2E9BA6",
                        "装饰条 / 互补品类 / 正向数据 / 图标 / 流程箭头",
                        "Accent rules, complementary series, positive values, icons, arrows",
                        role="brand")),
        ("grayblue", Swatch("grayblue", "灰蓝 · 中性", "Slate Blue", "#6B86A3",
                            "副文 / 坐标轴标签 / 第三序列 / 无效应象限",
                            "Secondary copy, axis labels, third series, null quadrants",
                            role="brand")),
        ("brick", Swatch("brick", "深砖红 · 警示", "Warning Brick", "#C0392B",
                         "仅“减少/替代”类关键数字。单页 ≤ 3%，全篇 ≤ 6%",
                         "Only decreasing / substitution numbers. <=3% per page, <=6% overall",
                         role="brand", budget="<=6% overall")),
        ("white", Swatch("white", "白 · 主背景", "Paper White", "#FFFFFF",
                         "页面底色 / 白卡", "Page background, plain cards", role="surface")),
        ("light", Swatch("light", "浅灰 · 卡底", "Mist Grey", "#F4F7FB",
                         "副卡片 / 图表容器 / 表格斑马", "Secondary cards, chart frames, zebra rows",
                         role="surface")),
        ("mint", Swatch("mint", "浅青 · 高亮底", "Tide Tint", "#E6F3F5",
                        "互补品类 / 关键结论条", "Complementary blocks, key takeaway bars",
                        role="surface")),
        ("pink", Swatch("pink", "浅红 · 警示底", "Warning Tint", "#FCE5E2",
                        "替代象限 / 负向数据卡", "Substitution quadrants, negative data cards",
                        role="surface")),
        ("line", Swatch("line", "线框灰", "Hairline", "#D6DCE5",
                        "描边 1px / 表格线 / 分隔线", "1px strokes, table rules, dividers",
                        role="surface")),
    ]
)

#: Three-step text hierarchy.
TEXT_COLORS: "OrderedDict[str, Swatch]" = OrderedDict(
    [
        ("t1", Swatch("t1", "文本主", "Ink", "#1A2230",
                      "正文主述、卡片标题", "Body copy, card titles", role="text")),
        ("t2", Swatch("t2", "文本副", "Body", "#4A5568",
                      "说明文字、注解", "Explanatory text, annotations", role="text")),
        ("t3", Swatch("t3", "文本辅", "Faint", "#8B97A8",
                      "页脚、单位、来源标注", "Footer, units, source notes", role="text")),
    ]
)

#: Role -> palette key.  Layout code addresses colours by role, never by hex.
ROLES: Dict[str, str] = {
    "primary": "navy",
    "accent": "teal",
    "neutral": "grayblue",
    "danger": "brick",
    "bg": "white",
    "surface": "light",
    "tint": "mint",
    "alert_tint": "pink",
    "stroke": "line",
    "ink": "t1",
    "body": "t2",
    "faint": "t3",
    # data semantics
    "up": "teal",
    "down": "brick",
    "flat": "navy",
    "complementary": "teal",
    "substitution": "brick",
    "null_effect": "grayblue",
    "neutral_number": "navy",
}

#: Share-of-ink budget used by the linter (percent of rendered area).
RATIO_BUDGET: Dict[str, object] = {
    "blue_family": (35, 50),   # navy + grayblue
    "white": (35, 55),
    "tint_family": (0, 20),    # light + mint
    "brick": (0, 6),           # hard ceiling
    "gold": (0, 0),            # hard ban
}

#: Machine-checkable bans.  ``kind=hex`` / ``hue`` / ``pattern``.
FORBIDDEN: List[Dict[str, object]] = [
    {"kind": "hue", "lo": 270, "hi": 345, "min_sat": 0.15,
     "reason_zh": "紫色 / 粉色 / 玫红一律禁用",
     "reason_en": "No purple, pink or rose"},
    {"kind": "hue", "lo": 30, "hi": 60, "min_sat": 0.45,
     "reason_zh": "金色禁用（含香槟金、土金）",
     "reason_en": "Gold is banned (including champagne and mustard)"},
    {"kind": "hue", "lo": 85, "hi": 165, "min_sat": 0.55,
     "reason_zh": "高饱和橙绿大色块禁用",
     "reason_en": "No large highly-saturated orange/green blocks"},
    {"kind": "hex", "value": "#000000",
     "reason_zh": "纯黑大底禁用", "reason_en": "No full black fills"},
]

#: Style-guide red lines that are not colour maths.
BANNED_MOTIFS_ZH = [
    "彩虹渐变 / 渐变作卡片背景",
    "3D、卡通、二次元、营销插画",
    "楷体行书毛笔字",
    "印章、烟花、金边装饰",
    "同排 3 张以上等宽卡片（Hero 页 0 张）",
]


# --------------------------------------------------------------------------- #
# Type system
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class TypeToken:
    """A step of the type scale.  ``px`` is authoritative, ``pt`` derived."""

    key: str
    name_zh: str
    px: float
    weight: str = "regular"          # bold | semibold | regular
    color: str = "t1"                # palette key
    letter_spacing: float = 0.0       # px
    line_height: float = 1.5
    use_zh: str = ""
    use_en: str = ""

    @property
    def pt(self) -> float:
        return round(self.px * 0.75, 2)

    @property
    def bold(self) -> bool:
        return self.weight in ("bold", "semibold")


#: Font stacks — the whole deck may only use two families (CJK + Latin).
FONTS: Dict[str, object] = {
    "cjk": ["Source Han Sans SC", "Noto Sans CJK SC", "Microsoft YaHei", "PingFang SC", "sans-serif"],
    "latin": ["Inter", "Source Sans 3", "Segoe UI", "Arial", "Helvetica", "sans-serif"],
    "serif": ["Times New Roman", "Source Han Serif SC", "serif"],   # cover / citation only
    "mono": ["SFMono-Regular", "Consolas", "Menlo", "monospace"],
    "max_families": 2,
    #: The pairing written into the .pptx.  Office files cannot carry web fonts,
    #: so we pick families that exist on a stock Windows/macOS install; decks can
    #: override this with ``meta.fonts: {latin: ..., cjk: ...}``.
    "ppt_latin": "Segoe UI",
    "ppt_cjk": "Microsoft YaHei",
}

TYPE_SCALE: "OrderedDict[str, TypeToken]" = OrderedDict(
    [
        ("cover_title", TypeToken("cover_title", "封面中文主标", 44, "bold", "navy", 0.0, 1.25,
                                  "封面主标题（中/英）", "Cover headline")),
        ("cover_subtitle", TypeToken("cover_subtitle", "封面英文副标", 26, "regular", "t1", 0.0, 1.35,
                                     "封面副标题", "Cover sub-headline")),
        ("cover_meta", TypeToken("cover_meta", "封面信息", 14, "regular", "t3", 0.0, 1.6,
                                 "作者 / 单位 / 日期", "Author, affiliation, date")),
        ("section_number_lg", TypeToken("section_number_lg", "章节大数字（大）", 72, "bold", "navy", 0.0, 1.0,
                                        "封面 / 核心结论页锚点", "Hero anchor number")),
        ("section_number", TypeToken("section_number", "章节大数字", 48, "bold", "teal", 0.0, 1.0,
                                     "科学问题 02 / 03", "Question number 02 / 03")),
        ("page_title", TypeToken("page_title", "页面主标", 30, "bold", "navy", 0.0, 1.25,
                                 "B 区主标题", "Page title (band B)")),
        ("kicker", TypeToken("kicker", "眉标", 14, "bold", "teal", 2.5, 1.4,
                             "01 · BACKGROUND 眉标，必须带字间距", "Section kicker, always letter-spaced")),
        ("page_subtitle", TypeToken("page_subtitle", "页面副标", 15, "regular", "grayblue", 0.0, 1.45,
                                    "一句话副题 / 英文原题", "Sub-title / English title")),
        ("card_title", TypeToken("card_title", "卡内小标", 18, "bold", "navy", 0.0, 1.35,
                                 "卡片标题", "Card title")),
        ("card_title_sm", TypeToken("card_title_sm", "卡内小标（小）", 16, "bold", "navy", 0.0, 1.35,
                                    "次级卡片标题", "Small card title")),
        ("card_body", TypeToken("card_body", "卡内正文", 14, "regular", "t2", 0.0, 1.58,
                                "卡片正文，下限 13px", "Card body, never below 13px")),
        ("card_body_sm", TypeToken("card_body_sm", "卡内正文（小）", 13, "regular", "t2", 0.0, 1.55,
                                   "密集列表", "Dense list text")),
        ("kpi_value", TypeToken("kpi_value", "KPI 巨数字", 44, "bold", "teal", 0.0, 1.05,
                                "升 = 青绿 / 降 = 砖红 / 中性 = 深蓝", "Anchor number")),
        ("kpi_value_sm", TypeToken("kpi_value_sm", "KPI 巨数字（小）", 32, "bold", "navy", 0.0, 1.05,
                                   "四卡并排时的次级数字", "Compact KPI number")),
        ("kpi_label", TypeToken("kpi_label", "KPI 标签", 12, "regular", "grayblue", 0.0, 1.4,
                                "数字上方标签", "Label above a number")),
        ("kpi_note", TypeToken("kpi_note", "KPI 脚注", 12, "regular", "t2", 0.0, 1.45,
                               "数字下方注解", "Note under a number")),
        ("table_head", TypeToken("table_head", "表头", 13, "bold", "white", 0.0, 1.35,
                                 "白字 + 深蓝底", "Table header")),
        ("table_cell", TypeToken("table_cell", "表格正文", 12.5, "regular", "t2", 0.0, 1.4,
                                 "表格单元", "Table cell")),
        ("node", TypeToken("node", "流程节点", 13, "bold", "white", 0.0, 1.3,
                           "节点文字", "Flow node label")),
        ("quote", TypeToken("quote", "金句", 22, "bold", "navy", 0.0, 1.45,
                            "结论页金句", "Closing quotation")),
        ("caption", TypeToken("caption", "注解 / 脚注", 11.5, "regular", "t3", 0.0, 1.45,
                              "来源、单位、表号", "Caption, unit, table number")),
        ("footer", TypeToken("footer", "页脚", 12, "regular", "t3", 0.0, 1.4,
                             "左下单位 / 来源", "Footer left")),
        ("page_number", TypeToken("page_number", "页码", 12, "bold", "navy", 0.0, 1.4,
                                  "右下 NN / 12", "Footer right")),
    ]
)

#: Hard typography rules the linter enforces.
TYPE_RULES: Dict[str, object] = {
    "min_px_body": 13,        # academic body lower bound
    "min_px_any": 11,         # smallest allowed text anywhere (captions)
    "carousel_line_height": (1.5, 1.6),
    "max_font_families": 2,
    "max_weights": 2,         # bold + regular
    "min_contrast": 4.5,      # WCAG AA for body copy
}

# --------------------------------------------------------------------------- #
# Component geometry
# --------------------------------------------------------------------------- #

RADIUS = {"card_sm": 6, "card_lg": 8, "chip": 999, "node": 6}
STROKE = {"hairline": 1.0, "emphasis": 2.0, "accent_bar": 5.0}
CARD_PADDING = {"sm": (14, 16, 14, 16), "md": (18, 20, 18, 20), "lg": (24, 28, 20, 28)}

KPI = {"value_sizes": [32, 44, 48, 72], "label_gap": 6, "note_gap": 4,
       "min_col_width": 150}

CHART = {
    "default_type": "bar",
    "grouping": "clustered",
    "height_px": (230, 400),
    "series_colors": ["navy", "teal", "grayblue", "brick"],
    "axis_color": "grayblue",
    "legend_color": "t2",
    "title_color": "navy",
    "data_label_color": "t1",
    "show_data_labels": True,
    "gridlines": None,
    "require_explicit_height": True,
}

FLOW = {"node_w": (110, 130), "node_h": 50, "arrow_px": 19, "gap_px": (8, 16)}

MATRIX = {"quadrant_w": 380, "quadrant_h": 190, "gap_px": 20, "center_dot": 20}

TABLE = {"head_fill": "navy", "head_text": "white", "zebra": "light",
         "grid": "line", "highlight": "mint", "highlight_neg": "pink"}

# --------------------------------------------------------------------------- #
# Page rhythm rules (style guide 06)
# --------------------------------------------------------------------------- #

RHYTHM_RULES: Dict[str, object] = {
    "hero_ratio": (4, 12),                 # 4 of 12 pages carry the peak
    "asymmetry_ratio": 0.83,               # >= 83% asymmetric layouts
    "equal_width_card_rows_max": 2,        # per deck
    "hero_equal_width_rows": 0,            # never on a hero page
    "no_three_valleys": True,
    "chart_pages_max_share": 0.40,         # chart-left + text-right combined
    "min_content_fill": 0.80,              # card fill ratio
    "min_anchor_px": 44,                   # one visual anchor per page
    "tint_family_max": 0.20,
}

#: Layouts that count as a "hero / peak" page by default.  ``hero`` is really a
#: property of the page, not the layout, so a deck may override it per page
#: (the reference deck promotes exactly one of its two chart pages).
HERO_LAYOUTS = ("cover", "key_findings", "closing")


def swatch(key: str) -> Swatch:
    """Look up a palette entry by key, accepting ``#RRGGBB`` passthroughs."""
    if key in PALETTE:
        return PALETTE[key]
    if key in TEXT_COLORS:
        return TEXT_COLORS[key]
    raise KeyError(f"unknown palette key: {key!r} (see tokens.PALETTE)")


def hex_of(key: str) -> str:
    """Resolve a palette key (or ``role`` name) to ``#RRGGBB`` uppercase."""
    if isinstance(key, str) and key.startswith("#"):
        return key.upper()
    if key in ROLES:
        key = ROLES[key]
    return swatch(key).hex


def type_token(key: str) -> TypeToken:
    if key not in TYPE_SCALE:
        raise KeyError(f"unknown type token: {key!r} (see tokens.TYPE_SCALE)")
    return TYPE_SCALE[key]


def allowed_hexes() -> List[str]:
    """Every colour a deck is permitted to draw with."""
    out: List[str] = []
    for s in list(PALETTE.values()) + list(TEXT_COLORS.values()):
        if s.hex not in out:
            out.append(s.hex)
    return out


def css_variables() -> str:
    """Emit the palette + type scale as CSS custom properties (HTML renderer)."""
    lines = [":root{"]
    for key, s in PALETTE.items():
        lines.append(f"  --do-{key}:{s.hex};")
    for key, s in TEXT_COLORS.items():
        lines.append(f"  --do-{key}:{s.hex};")
    lines.append(f"  --do-margin:{SAFE_MARGIN_PX}px;")
    lines.append(f"  --do-gap:{CARD_GAP_PX}px;")
    for key, t in TYPE_SCALE.items():
        lines.append(f"  --do-{key}:{t.px}px;")
    lines.append("}")
    return "\n".join(lines)


def summary() -> Dict[str, object]:
    """Compact, JSON-serialisable description of the whole system."""
    return {
        "name": NAME,
        "name_zh": NAME_ZH,
        "version": VERSION,
        "canvas": CANVAS,
        "safe_margin_px": SAFE_MARGIN_PX,
        "card_gap_px": CARD_GAP_PX,
        "bands": BANDS,
        "palette": {k: {"hex": v.hex, "name_zh": v.name_zh, "name_en": v.name_en} for k, v in PALETTE.items()},
        "text_colors": {k: {"hex": v.hex, "name_zh": v.name_zh} for k, v in TEXT_COLORS.items()},
        "roles": ROLES,
        "type_scale": {k: {"px": t.px, "pt": t.pt, "weight": t.weight, "color": t.color}
                       for k, t in TYPE_SCALE.items()},
        "ratio_budget": RATIO_BUDGET,
        "type_rules": TYPE_RULES,
        "rhythm_rules": RHYTHM_RULES,
    }
