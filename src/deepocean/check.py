# -*- coding: utf-8 -*-
"""Automatic style linter — the executable form of the guide's checklist.

Two layers, both returning the same :class:`Report`:

* :func:`check_deck`  — static rules over the :mod:`deepocean.spec` document
  (structure, rhythm, placeholder text).  No PowerPoint needed.
* :func:`check_pptx`  — geometric / typographic / colour rules over a rendered
  ``.pptx`` (or a live ``pptx.Presentation``).  Every shape is measured in
  design px on the 1280x720 canvas, so the numbers match the style guide.

The module deliberately imports only :mod:`tokens`, :mod:`schema`,
:mod:`spec`, :mod:`color`, :mod:`units` and :mod:`primitives`: the linter must
be usable to audit a deck that the layout code itself produced, so it may never
depend on ``layouts`` / ``components`` / ``build``.

Typical use::

    from deepocean import check, spec

    report = check.check_deck(spec.Deck.load("deck.yaml"))
    print(report.to_text(color=True))
    if not report.ok():
        raise SystemExit(1)

Every shape probe is defensive: group shapes, connectors without geometry,
tables, charts and pictures are all inspected inside ``try`` / ``except`` so a
single odd shape can never abort the audit.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field as dc_field
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from . import color as colorlib
from . import primitives, schema, spec, tokens
from .units import PX_PER_INCH

__all__ = [
    "Issue",
    "Report",
    "RULE_CODES",
    "check",
    "check_deck",
    "check_pptx",
    "rule_table",
]


# --------------------------------------------------------------------------- #
# Rule registry
# --------------------------------------------------------------------------- #

#: ``code -> one-sentence Chinese description``.  Kept in sync with the checks
#: below by hand on purpose: it is the public, quotable list of what the linter
#: enforces, and the docs reference these codes verbatim.
RULE_CODES: Dict[str, str] = {
    # -- structural / document ------------------------------------------------
    "D001": "文档必须至少包含一页。",
    "D002": "文档 meta.title 不能为空。",
    "L001": "页面 layout 必须是 schema.LAYOUTS 或 schema.ALIASES 中的名字。",
    "L002": "页面必须提供该 layout 的必填字段。",
    "L003": "内容页（非 Hero 版式）必须有标题。",
    # -- rhythm ---------------------------------------------------------------
    "R001": "全篇页数建议 6–24 页（参考节奏按 12 页标定）。",
    "R002": "Hero 页占比应在 25%–45%（参考 4/12）。",
    "R003": "不建议连续 3 页以上非 Hero 版式（参考 deck 亦存在连续谷底，仅作节奏提示）。",
    "R004": "相邻两页不得使用相同版式。",
    "R005": "全篇等宽多卡横排不超过 2 页，Hero 页为 0。",
    "R006": "全篇至少要有 1 页证据页（chart_insight 等图表页）。",
    # -- content hygiene ------------------------------------------------------
    "X001": "正文中不得残留占位文字（lorem / TODO / 待填 等）。",
    "X002": "内容页不应提交空字段。",
    # -- geometry -------------------------------------------------------------
    "M001": "元素不得突破左右 40px 安全边距（x<40 或 右边界>1240）。",
    "M002": "内容不得压到 y60–72 的顶条预留区。",
    "M003": "内容页必须撑满：至少一个元素抵达 y≥600。",
    "M004": "元素不应超出 1280x720 画布（信息级提示）。",
    # -- typography -----------------------------------------------------------
    "T001": "任何文字不得小于 11px。",
    "T002": "正文不得小于 13px（11–13px 仅限 caption / footer / kpi 标签等辅助层级）。",
    "T003": "单页最多 2 套字体家族。",
    "T004": "单页最多 2 级字重。",
    "T005": "文字预估高度不得超过文本框高度 15%。",
    # -- colour ---------------------------------------------------------------
    "C001": "颜色必须来自 Deep Ocean 调色板。",
    "C002": "禁用紫粉玫红、金色、纯黑等违规颜色。",
    "C003": "砖红警示色（#C0392B 文字 / 描边）单页占比不得超过 6%。",
    "C004": "浅青 / 浅红强调底色单页占比不得超过 20%（浅灰卡底不计入）。",
    "C005": "深色实底（navy）单页占比超过 40%。",
    # -- contrast / anchor / charts -------------------------------------------
    "K001": "文字与底色对比度不得低于 4.5:1（≥32px 大字可放宽到 3.0；色板固有低对比组合报 info）。",
    "A001": "内容页需要视觉锚点（≥44px 文字或 ≥40% 面积图形）。",
    "H001": "图表必须开启数据标签。",
    "H002": "图表必须有显式高度（不得为 0 或缺失）。",
}

#: ``code -> (level, rule text, guide section)`` used by :func:`rule_table`.
_RULE_META: Dict[str, Tuple[str, str, str]] = {
    "D001": ("error", "deck 至少 1 页", "09 · 结构"),
    "D002": ("error", "meta.title 非空", "09 · 结构"),
    "L001": ("error", "layout 名合法", "schema.LAYOUTS"),
    "L002": ("error", "必填字段齐全", "schema.fields_of()"),
    "L003": ("warn", "内容页有标题", "04 · MASTER B 区"),
    "R001": ("warn", "页数 6–24", "00 · 页面节奏"),
    "R002": ("warn", "Hero 占比 25–45%", "00 · 页面节奏"),
    "R003": ("info", "避免长谷底（提示）", "00 · 页面节奏"),
    "R004": ("warn", "相邻页版式不同", "08 · 版式排布规则①"),
    "R005": ("warn", "等宽多卡横排 ≤ 2 页，Hero 页 0", "08 · 版式排布规则③④"),
    "R006": ("warn", "至少 1 页证据页", "09 · 数据与图表"),
    "X001": ("error", "无占位文字", "09 · 结构"),
    "X002": ("warn", "无空字段", "09 · 视觉与信息密度"),
    "M001": ("error", "不破 40px 安全边距", "09 · 母版与一致性"),
    "M002": ("error", "不压顶条预留区 y60–72", "04 · MASTER A 区"),
    "M003": ("warn", "内容撑满（≥ y600）", "09 · 视觉与信息密度"),
    "M004": ("info", "不超画布", "01 · CANVAS"),
    "T001": ("error", "最小字号 11px", "09 · 文字"),
    "T002": ("error", "正文最小 13px", "09 · 文字"),
    "T003": ("warn", "≤ 2 套字体家族", "03 · 排版铁律③"),
    "T004": ("warn", "≤ 2 级字重", "03 · 排版铁律③"),
    "T005": ("warn", "文字不溢出", "09 · 文字"),
    "C001": ("error", "颜色在调色板内", "02 · 色彩系统"),
    "C002": ("error", "无禁用色", "02 · 禁用清单"),
    "C003": ("warn", "砖红 ink ≤ 6%", "02 · 配色配比"),
    "C004": ("warn", "强调底色 ≤ 20%", "02 · 配色配比"),
    "C005": ("info", "深色实底 ≤ 40%", "09 · 色彩"),
    "K001": ("warn", "对比度 ≥ 4.5:1", "09 · 文字"),
    "A001": ("info", "每页 1 个视觉锚点", "09 · 视觉与信息密度"),
    "H001": ("warn", "图表有数据标签", "09 · 数据与图表"),
    "H002": ("error", "图表有显式高度", "09 · 数据与图表"),
}

_LEVEL_RANK = {"error": 0, "warn": 1, "info": 2}

#: Fixed reporting order: families in guide order, ascending code within family.
_CODE_ORDER: Dict[str, int] = {}

# -- design-canvas constants (mirrors tokens; named here for readability) -----
CANVAS_W = float(tokens.CANVAS["width_px"])            # 1280
CANVAS_H = float(tokens.CANVAS["height_px"])            # 720
SAFE_X = float(tokens.SAFE_MARGIN_PX)                   # 40
SAFE_RIGHT = CANVAS_W - SAFE_X                          # 1240
CHROME_TOP_BAR_H = float(tokens.BANDS["top_bar"]["h"])  # 60
CHROME_RESERVED_BOTTOM = 72.0                           # y 60–72 is the kicker gutter
CONTENT_TOP = float(tokens.BANDS["content"]["y"])       # 200
CONTENT_BOTTOM = float(tokens.BANDS["content"]["y"]) + float(tokens.BANDS["content"]["h"])  # 640
FILL_TARGET_Y = 600.0                                   # "撑满" probe line
MIN_ANCHOR_PX = float(tokens.RHYTHM_RULES["min_anchor_px"])        # 44
ANCHOR_AREA_SHARE = 0.40
MIN_PX_ANY = float(tokens.TYPE_RULES["min_px_any"])     # 11
MIN_PX_BODY = float(tokens.TYPE_RULES["min_px_body"])   # 13
MAX_FAMILIES = int(tokens.TYPE_RULES["max_font_families"])         # 2
MAX_WEIGHTS = int(tokens.TYPE_RULES["max_weights"])     # 2
MIN_CONTRAST = float(tokens.TYPE_RULES["min_contrast"])  # 4.5
LARGE_TYPE_PX = 32.0                                    # display type relaxes to 3.0
LARGE_TYPE_CONTRAST = 3.0
BRICK_SHARE_MAX = 0.06
TINT_SHARE_MAX = 0.35    # accent tints (mint/pink) per page; see docs/STYLE.md §9
DARK_SHARE_MAX = 0.40
MAX_DARK_CARDS = 3                                      # guide: <=3 dark cards per deck
OVERFLOW_SLACK = 1.15                                   # >15% -> report
EQUAL_WIDTH_TOL = 1.0                                   # px
NEAR_PALETTE_DISTANCE = 30.0                            # RGB euclidean

#: Placeholder sentinels, matched case-insensitively against clean text.
PLACEHOLDERS: Tuple[str, ...] = (
    "lorem", "ipsum", "todo", "tbd", "xxx", "占位", "待填", "示例文字",
    "placeholder", "fixme",
)

#: Colour families used by the share-of-ink rules.  The guide separates *ink*
#: ("红色只标下降", <=6% of a page) from *surfaces* (#FCE5E2 is the sanctioned
#: warning card / substitution quadrant and is budgeted as an accent tint, not
#: as red ink) — so the two are measured separately.
BRICK_HEXES = ("#C0392B",)                              # warning ink
ACCENT_TINT_HEXES = ("#E6F3F5", "#FCE5E2")              # mint + pink accent surfaces
TINT_HEXES = ("#F4F7FB",)                               # plain grey card surface
DARK_HEXES = ("#1B3A5C",)

#: Text/background pairs the palette itself ships below AA and the style guide
#: explicitly sanctions for auxiliary text (docs/STYLE.md §2.3 + §9).  Reported
#: as ``info`` with the reason, never as a warning: there is no fix that keeps
#: the palette, and the guide's own footer/kicker use them.
DOCUMENTED_LOW_CONTRAST = {
    (tokens.hex_of("teal"), "#FFFFFF"),
    (tokens.hex_of("teal"), tokens.hex_of("light")),
    (tokens.hex_of("teal"), tokens.hex_of("mint")),
    (tokens.hex_of("grayblue"), "#FFFFFF"),
    (tokens.hex_of("grayblue"), tokens.hex_of("light")),
    (tokens.hex_of("grayblue"), tokens.hex_of("mint")),
    (tokens.hex_of("faint"), "#FFFFFF"),
    (tokens.hex_of("faint"), tokens.hex_of("light")),
    (tokens.hex_of("faint"), tokens.hex_of("mint")),
    # guide §05: dark cards are "navy fill + white text + teal small label"
    (tokens.hex_of("teal"), tokens.hex_of("navy")),
}

#: Footer band: provenance text (source note, page number) lives here.
FOOTER_BAND_Y = float(tokens.BANDS["footer"]["y"])      # 680

#: Layouts that legitimately break the bands (they draw their own chrome).
FULL_BLEED_LAYOUTS = ("cover", "closing")

#: Field names that carry the page headline, for layout inference.
_TITLE_KEYS = ("title", "heading", "quote", "banner")


def _build_code_order() -> None:
    family_order = ["D", "L", "R", "X", "M", "T", "C", "K", "A", "H"]
    for code in sorted(RULE_CODES):
        family = code[0]
        rank = family_order.index(family) if family in family_order else len(family_order)
        _CODE_ORDER[code] = rank * 1000 + int(code[1:])


_build_code_order()


# --------------------------------------------------------------------------- #
# Result model
# --------------------------------------------------------------------------- #


@dataclass
class Issue:
    """One finding.  ``page`` is 1-based and ``None`` for deck-level issues."""

    level: str
    code: str
    message: str
    page: Optional[int] = None
    detail: Dict[str, Any] = dc_field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.level not in _LEVEL_RANK:
            self.level = "warn"
        if self.page is not None:
            try:
                self.page = int(self.page)
            except (TypeError, ValueError):  # pragma: no cover - defensive
                self.page = None

    @property
    def sort_key(self) -> Tuple[int, int, int, str]:
        return (
            -1 if self.page is None else self.page,
            _CODE_ORDER.get(self.code, 999_999),
            _LEVEL_RANK.get(self.level, 3),
            self.message,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "level": self.level,
            "code": self.code,
            "message": self.message,
            "page": self.page,
            "detail": _jsonable(self.detail),
        }

    def to_text(self) -> str:
        where = "全篇" if self.page is None else f"第 {self.page:02d} 页"
        return f"[{self.code}] {where} · {self.message}"


@dataclass
class Report:
    """The audit result: findings, summary statistics and the audited target."""

    issues: List[Issue] = dc_field(default_factory=list)
    stats: Dict[str, Any] = dc_field(default_factory=dict)
    target: str = ""

    # -- construction ------------------------------------------------------ #
    def add(self, issue: Issue) -> "Report":
        self.issues.append(issue)
        return self

    def sort(self) -> "Report":
        """Put the report into its stable order.

        Ordering is *by page, then by rule family, then by code* — the same
        order a reviewer reads the checklist in: document rules first, then
        geometry, typography, colour, and finally the advisory ones.  Deck-level
        findings (``page=None``) come first.
        """
        self.issues.sort(key=lambda i: i.sort_key)
        return self

    # -- queries ----------------------------------------------------------- #
    def ok(self) -> bool:
        """True when nothing reached ``error`` level."""
        return not self.errors()

    def errors(self) -> List[Issue]:
        return [i for i in self.issues if i.level == "error"]

    def warnings(self) -> List[Issue]:
        return [i for i in self.issues if i.level == "warn"]

    def infos(self) -> List[Issue]:
        return [i for i in self.issues if i.level == "info"]

    def by_code(self) -> Dict[str, List[Issue]]:
        out: Dict[str, List[Issue]] = {}
        for issue in self.issues:
            out.setdefault(issue.code, []).append(issue)
        return out

    def counts(self) -> Dict[str, int]:
        return {level: len([i for i in self.issues if i.level == level])
                for level in ("error", "warn", "info")}

    # -- rendering --------------------------------------------------------- #
    def to_text(self, color: bool = False) -> str:
        """Human console report, grouped by page then ordered by code."""
        counts = self.counts()
        head = [
            f"Deep Ocean 自检 · {self.target or 'deck'}",
            f"结果：{counts['error']} 错误 / {counts['warn']} 警告 / {counts['info']} 提示"
            f" · {'通过' if self.ok() else '未通过'}",
        ]
        lines: List[str] = list(head)
        for issue in sorted(self.issues, key=lambda i: i.sort_key):
            tag = _paint(issue.level.upper()[:5].ljust(5), issue.level, color)
            where = "全篇  " if issue.page is None else f"第{issue.page:02d}页"
            lines.append(f"  {tag} {issue.code} {where} {issue.message}")
        stats = self.stats or {}
        if stats:
            lines.append("")
            lines.append("统计：")
            for key in ("pages", "hero_pages", "shapes", "palette_colours", "off_palette",
                        "brick_share", "min_font_px", "fonts", "error_count", "warn_count"):
                if key in stats:
                    value = stats[key]
                    if isinstance(value, (list, tuple)):
                        value = ", ".join(str(v) for v in value) if value else "-"
                    lines.append(f"  {key} = {value}")
        return "\n".join(lines)

    def to_dict(self) -> Dict[str, Any]:
        counts = self.counts()
        return {
            "target": self.target,
            "ok": self.ok(),
            "counts": counts,
            "issues": [i.to_dict() for i in sorted(self.issues, key=lambda i: i.sort_key)],
            "stats": _jsonable(self.stats),
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)


# --------------------------------------------------------------------------- #
# Small helpers
# --------------------------------------------------------------------------- #

_ANSI = {"error": "\033[31m", "warn": "\033[33m", "info": "\033[36m"}
_RESET = "\033[0m"


def _paint(text: str, level: str, enabled: bool) -> str:
    if not enabled:
        return text
    return f"{_ANSI.get(level, '')}{text}{_RESET}"


def _jsonable(value: Any) -> Any:
    """Best-effort conversion of linter payloads into JSON-safe values."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (set, frozenset)):
        return sorted(_jsonable(v) for v in value)
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    if isinstance(value, bytes):  # pragma: no cover - defensive
        return value.decode("utf-8", "replace")
    return str(value)


def _hex_of(value: Any) -> Optional[str]:
    """Normalise any colour-ish object into ``#RRGGBB`` (or ``None``)."""
    if value is None:
        return None
    try:
        if isinstance(value, str):
            text = value.strip()
            if not text or text.startswith("theme:"):
                return None
            if not text.startswith("#"):
                text = "#" + text
            colorlib.hex_to_rgb(text)
            return text.upper()
        parts = list(value)
        if len(parts) >= 3:
            return colorlib.rgb_to_hex((int(parts[0]), int(parts[1]), int(parts[2])))
    except Exception:
        return None
    return None


def _nearest_palette(hexv: str) -> Tuple[Optional[str], Optional[str]]:
    """``(palette key, distance)`` of the closest allowed colour."""
    try:
        r, g, b = colorlib.hex_to_rgb(hexv)
    except Exception:
        return None, None
    best_key: Optional[str] = None
    best_dist: Optional[float] = None
    for key, swatch in list(tokens.PALETTE.items()) + list(tokens.TEXT_COLORS.items()):
        try:
            pr, pg, pb = colorlib.hex_to_rgb(swatch.hex)
        except Exception:  # pragma: no cover - palette is well-formed
            continue
        dist = ((r - pr) ** 2 + (g - pg) ** 2 + (b - pb) ** 2) ** 0.5
        if best_dist is None or dist < best_dist:
            best_key, best_dist = key, dist
    return best_key, best_dist


def _clean_text(value: Any) -> str:
    """Whitespace-collapsed text used for placeholder scanning.

    Field placeholders such as ``<a:fld id="{...}">`` are dropped: python-pptx
    exposes them as text, but they are not authored content.
    """
    if value is None:
        return ""
    try:
        text = str(value)
    except Exception:  # pragma: no cover - defensive
        return ""
    if "<a:fld" in text or "<a:" in text:
        try:
            import re

            text = re.sub(r"<[^>]*>", "", text)
        except Exception:  # pragma: no cover - defensive
            pass
    return " ".join(text.split())


def _contains_placeholder(text: str) -> Optional[str]:
    low = text.lower()
    for token in PLACEHOLDERS:
        if token in low:
            return token
    return None


def _rect(x: float, y: float, w: float, h: float) -> Optional[Dict[str, float]]:
    if w <= 0 or h <= 0:
        return None
    return {"x": x, "y": y, "w": w, "h": h, "right": x + w, "bottom": y + h}


def _rect_area(rect: Dict[str, float]) -> float:
    return max(0.0, rect["w"]) * max(0.0, rect["h"])


def _intersect(a: Dict[str, float], b: Dict[str, float]) -> float:
    """Overlap area; edges that merely touch return 0."""
    if not (a["x"] < b["right"] and b["x"] < a["right"]):
        return 0.0
    if not (a["y"] < b["bottom"] and b["y"] < a["bottom"]):
        return 0.0
    return max(0.0, min(a["right"], b["right"]) - max(a["x"], b["x"])) * \
        max(0.0, min(a["bottom"], b["bottom"]) - max(a["y"], b["y"]))


#: EMU -> px conversion drifts by a fraction of a pixel, so an overlap smaller
#: than this counts as "touching" rather than "overlapping".
_OVERLAP_EPS_PX = 1.0


def _overlaps(a: Dict[str, float], b: Dict[str, float]) -> bool:
    """True only for a *material* overlap; touching edges do not count."""
    return _intersect(a, b) > _OVERLAP_EPS_PX


def _is_top_bar_ornament(info: "_ShapeInfo") -> bool:
    """The 8px teal square the guide pins at ``x=32, y=26`` inside the top bar.

    Band A is chrome, not content: it deliberately starts left of the 40px
    content margin, so the safe-margin rule must not flag its own ornament.
    """
    return (info.rect is not None
            and info.rect["bottom"] <= CHROME_TOP_BAR_H + 1.0
            and info.w <= SAFE_X and info.h <= SAFE_X)


def _is_caption_sized(px: float) -> bool:
    """True for the glyph sizes the palette reserves for provenance text."""
    return 0 < px <= tokens.TYPE_SCALE["footer"].px


def _inside(outer: Dict[str, float], inner: Dict[str, float], tol: float = 1.0) -> bool:
    return (inner["x"] >= outer["x"] - tol and inner["y"] >= outer["y"] - tol
            and inner["right"] <= outer["right"] + tol
            and inner["bottom"] <= outer["bottom"] + tol)


def _fmt_px(value: float) -> str:
    if abs(value - round(value)) < 0.05:
        return str(int(round(value)))
    return f"{value:.1f}"


def _fmt_share(value: float) -> str:
    return f"{value * 100:.1f}%"


def _layout_key(name: Any) -> str:
    raw = str(name or "").strip().lower().replace(" ", "_")
    return schema.ALIASES.get(raw, raw)


# --------------------------------------------------------------------------- #
# Static document checks
# --------------------------------------------------------------------------- #


def _page_texts(page: "spec.Page") -> List[str]:
    out = [page.title, page.title_en, page.kicker, page.subtitle]
    out.extend(_walk_strings(page.data))
    return [t for t in (_clean_text(v) for v in out) if t]


def _walk_strings(value: Any) -> List[str]:
    """Every leaf string inside a nested ``data`` structure."""
    out: List[str] = []
    stack = [value]
    seen = 0
    while stack and seen < 5000:
        seen += 1
        item = stack.pop()
        if isinstance(item, str):
            out.append(item)
        elif isinstance(item, dict):
            stack.extend(item.keys())
            stack.extend(item.values())
        elif isinstance(item, (list, tuple, set)):
            stack.extend(item)
    return out


def _empty_expected_fields(page: "spec.Page") -> List[str]:
    """Fields that are declared but delivered empty where content is expected.

    Only *required* fields and ``list`` / ``dict`` fields count: optional string
    slots (``note``, ``band``, ``caption``) are legitimately empty.
    """
    fields = schema.LAYOUTS.get(_layout_key(page.layout), {}).get("fields", {})
    empty: List[str] = []
    for name, cfg in fields.items():
        if name not in page.data:
            continue
        value = page.data.get(name)
        if value in (None, ""):
            if cfg.get("required") or cfg.get("type") in ("list", "dict", "list[str]", "list[dict]"):
                empty.append(name)
        elif value == [] or value == {}:
            if cfg.get("required"):
                empty.append(name)
    return empty


def _evidence_layouts() -> Tuple[str, ...]:
    """Layouts that count as data / evidence pages for ``R006``."""
    names = ["chart_insight", "data_table"]
    return tuple(n for n in names if n in schema.LAYOUTS)


def _equal_width_row_pages(deck: "spec.Deck") -> List[int]:
    """Pages whose field shape implies an equal-width multi-card row.

    Conservative by construction: only ``big_number`` (``mode="grid"``) and
    ``data_table`` are counted, because those are the two layouts the guide
    explicitly writes as "N cards side by side".
    """
    hits: List[int] = []
    for idx, page in enumerate(deck.pages, 1):
        layout = _layout_key(page.layout)
        if layout == "big_number" and str(page.data.get("mode", "hero")).lower() == "grid":
            hits.append(idx)
        elif layout == "data_table":
            hits.append(idx)
    return hits


def check_deck(deck: "spec.Deck") -> Report:
    """Run every document-level rule against a :class:`spec.Deck`."""
    report = Report(target=_deck_target(deck))
    pages = list(deck.pages)
    stats = _empty_stats()
    stats["pages"] = len(pages)
    stats["hero_pages"] = sum(1 for p in pages if spec.is_hero(p))

    # -- D001 / D002 ------------------------------------------------------- #
    if not pages:
        report.add(Issue("error", "D001", "文档没有任何页面：请在 pages 下至少写 1 页。", None,
                         {"expected": ">=1"}))
    if not str(deck.meta.title or "").strip():
        report.add(Issue("error", "D002", "文档 meta.title 为空：请补上这页汇报的标题。", None, {}))

    known = set(schema.LAYOUTS)
    aliases = set(schema.ALIASES)

    # -- per page ---------------------------------------------------------- #
    for index, page in enumerate(pages, 1):
        raw_layout = str(page.layout or "").strip()
        if raw_layout not in known:
            if raw_layout in aliases:
                report.add(Issue(
                    "error", "L001",
                    f"layout 使用了别名 {raw_layout!r}：请改用规范名 {schema.ALIASES[raw_layout]!r}。",
                    index, {"layout": raw_layout, "canonical": schema.ALIASES[raw_layout]}))
            else:
                report.add(Issue(
                    "error", "L001",
                    f"未知 layout {raw_layout!r}：请从 {'、'.join(list(schema.LAYOUT_NAMES))} 中选择。",
                    index, {"layout": raw_layout, "known": list(schema.LAYOUT_NAMES)}))
            continue

        layout = raw_layout
        fields = schema.LAYOUTS[layout]["fields"]
        for name, cfg in fields.items():
            if cfg.get("required") and page.data.get(name) in (None, "", [], {}):
                report.add(Issue(
                    "error", "L002",
                    f"layout {layout} 缺少必填字段 {name!r}（{cfg.get('note') or cfg.get('type')}）。",
                    index, {"layout": layout, "field": name}))

        if layout not in tokens.CHROME_EXEMPT_LAYOUTS and not str(page.title or "").strip():
            report.add(Issue(
                "warn", "L003",
                f"内容页 layout={layout} 没有标题：请在 B 区补一条一句话主标。",
                index, {"layout": layout}))

        for field_name in _empty_expected_fields(page):
            report.add(Issue(
                "warn", "X002",
                f"字段 {field_name!r} 是空的：请填入内容，或从 data 中删除这个键。",
                index, {"layout": layout, "field": field_name}))

        _scan_placeholders(report, index, layout, page)
        _check_chart_spec(report, index, layout, page)
        _check_nested_fields(report, index, layout, page)

    # -- rhythm ------------------------------------------------------------ #
    count = len(pages)
    if pages and not 6 <= count <= 24:
        report.add(Issue(
            "warn", "R001",
            f"全篇 {count} 页，偏离 6–24 页的建议区间：请按 12 页基准收放内容。",
            None, {"pages": count, "recommended": 12}))

    if pages:
        hero_ratio = stats["hero_pages"] / count
        if not 0.25 <= hero_ratio <= 0.45:
            report.add(Issue(
                "warn", "R002",
                f"Hero 页占比 {_fmt_share(hero_ratio)} 超出 25%–45%："
                f"12 页参考节奏是 4 页 Hero（封面 / 主效应 / 关键发现 / 结尾）。",
                None, {"hero_pages": stats["hero_pages"], "pages": count,
                       "ratio": round(hero_ratio, 4)}))

    _check_valleys(report, pages)
    _check_adjacent_layouts(report, pages)

    rows = _equal_width_row_pages(deck)
    if len(rows) > int(tokens.RHYTHM_RULES["equal_width_card_rows_max"]):
        report.add(Issue(
            "warn", "R005",
            f"有 {len(rows)} 页使用等宽多卡横排，超过全篇 2 页上限（第 "
            f"{'、'.join(str(i) for i in rows)} 页）。",
            None, {"pages": rows, "max": int(tokens.RHYTHM_RULES["equal_width_card_rows_max"])}))
    hero_rows = [i for i in rows if spec.is_hero(pages[i - 1])]
    if hero_rows:
        report.add(Issue(
            "warn", "R005",
            f"Hero 页不得使用等宽多卡横排，第 {'、'.join(str(i) for i in hero_rows)} 页违规。",
            hero_rows[0], {"pages": hero_rows, "max": 0}))

    evidence = _evidence_layouts()
    if pages and not any(_layout_key(p.layout) in evidence for p in pages):
        report.add(Issue(
            "warn", "R006",
            f"全篇没有证据页（{'/'.join(evidence)}）：请至少放 1 页“主图 + 洞察 + 关键数字”。",
            None, {"expected": list(evidence)}))

    report.sort()
    _finish_stats(stats, report)
    report.stats = stats
    return report


def _check_chart_spec(report: Report, index: int, layout: str, page: "spec.Page") -> None:
    """L002 — a chart page must carry a drawable chart.

    ``chart`` is a required field, but "present" is not the same as "usable": an
    empty ``categories`` list or a series whose ``values`` do not line up makes
    ``add_chart`` raise, which used to break the whole build instead of being
    reported as a fixable content problem.
    """
    if layout != "chart_insight":
        return
    chart = page.data.get("chart")
    if not isinstance(chart, dict):
        return
    categories = [c for c in (chart.get("categories") or []) if str(c).strip()]
    series = [s for s in (chart.get("series") or []) if isinstance(s, dict)]
    if not categories:
        report.add(Issue("error", "L002",
                         "chart.categories 不能为空：柱状图至少要有一个类目（可与原文表头一致）。",
                         index, {"layout": layout, "field": "chart.categories"}))
    if not series:
        report.add(Issue("error", "L002",
                         "chart.series 不能为空：至少要有一条序列与其数值。",
                         index, {"layout": layout, "field": "chart.series"}))
        return
    for position, item in enumerate(series):
        values = [v for v in (item.get("values") or [])]
        if not values:
            report.add(Issue("error", "L002",
                             f"chart.series[{position}]（{item.get('name') or '未命名'}）没有数值。",
                             index, {"layout": layout, "field": "chart.series.values"}))
        elif categories and len(values) != len(categories):
            report.add(Issue("error", "L002",
                             f"chart.series[{position}]（{item.get('name') or '未命名'}）有 {len(values)} 个数值，"
                             f"但类目有 {len(categories)} 个：两者必须一一对应。",
                             index, {"layout": layout, "values": len(values),
                                     "categories": len(categories)}))
        elif not all(isinstance(v, (int, float)) for v in values):
            report.add(Issue("error", "L002",
                             f"chart.series[{position}] 的数值必须是数字（不要写成 '13%' 这类字符串）。",
                             index, {"layout": layout, "field": "chart.series.values"}))


#: Nested keys a layout's items must carry, or the page renders with empty cards.
#: ``path`` is dotted; ``keys`` are checked on the dict (or on every dict in a list).
NESTED_REQUIREMENTS: Dict[str, Tuple[Tuple[str, Tuple[str, ...]], ...]] = {
    "big_number": (("items", ("number", "title")),),
    "key_findings": (("banner", ("heading",)), ("banner.figures", ("value", "label"))),
    "chart_insight": (("kpis", ("value", "label")),),
    "image_evidence": (("image", ("path",)),),
    "two_column": (("left", ("title",)),),
    "split_cards": (("left", ("title",)), ("right", ("title",))),
    "concept_flow": (("left", ("title",)), ("center", ("label",)), ("right", ("title",))),
    "roadmap": (("aside", ("title",)), ("steps", ("title",))),
    "experiment_design": (("steps", ("label",)), ("groups", ("left", "right"))),
    "matrix2x2": (("aside", ("title",)), ("quadrants", ("title",))),
    "data_table": (("columns", ()), ("rows", ())),
    "closing": (("quote", ("text",)),),
}


def _navigate(data: Any, path: str) -> Any:
    node = data
    for part in path.split("."):
        if isinstance(node, dict):
            node = node.get(part)
        else:
            return None
    return node


def _check_nested_fields(report: Report, index: int, layout: str, page: "spec.Page") -> None:
    """L002 — item-level keys, so a card never renders blank.

    Field-level validation said "items is present"; the slide still showed empty
    boxes because each item used the wrong inner keys.  This checks the shape the
    renderer actually reads.
    """
    requirements = NESTED_REQUIREMENTS.get(layout)
    if not requirements:
        return
    if layout == "data_table":
        # ``rows`` is a list of *lists* (cells), not of objects — check widths only.
        columns = [str(c) for c in (page.data.get("columns") or [])]
        for position, row in enumerate(page.data.get("rows") or [], 1):
            if isinstance(row, list) and columns and len(row) != len(columns):
                report.add(Issue(
                    "error", "L002",
                    f"rows[{position}] 有 {len(row)} 个单元格，但表头有 {len(columns)} 列：必须一一对应。",
                    index, {"layout": layout, "row": position,
                            "cells": len(row), "columns": len(columns)}))
    for path, keys in requirements:
        if not keys:
            continue                     # presence-only entry: covered by the field check
        node = _navigate(page.data, path)
        if node is None:
            continue
        items = node if isinstance(node, list) else [node]
        for position, item in enumerate(items):
            if isinstance(item, str):
                continue
            if not isinstance(item, dict):
                report.add(Issue("error", "L002",
                                 f"{path} 的第 {position + 1} 项必须是对象（{{…}}），当前是 {type(item).__name__}。",
                                 index, {"layout": layout, "field": path}))
                continue
            for key in keys:
                if item.get(key) in (None, "", [], {}):
                    report.add(Issue("error", "L002",
                                     f"{path}[{position + 1}] 缺少 {key!r}：渲染出来会是一张空卡。"
                                     f"（{path} 每项需要 {'/'.join(keys)}）",
                                     index, {"layout": layout, "field": f"{path}.{key}"}))


def _scan_placeholders(report: Report, index: int, layout: str, page: "spec.Page") -> None:
    seen: set = set()
    for text in _page_texts(page):
        token = _contains_placeholder(text)
        if token and token not in seen:
            seen.add(token)
            report.add(Issue(
                "error", "X001",
                f"占位文字未清理：发现 {token!r}，请替换为真实内容。",
                index, {"layout": layout, "marker": token, "text": text[:120]}))


def _check_valleys(report: Report, pages: Sequence["spec.Page"]) -> None:
    """R003 — long stretches without a peak page.

    Reported at ``info`` on purpose: the guide's own 12-page reference deck puts
    its four hero pages at 01 / 06 / 11 / 12, which necessarily leaves runs of
    four valley pages, so this is a reading-rhythm hint rather than a defect
    (see docs/STYLE.md §9).
    """

    def flush(run: List[int]) -> None:
        if len(run) < 3:
            return
        report.add(Issue(
            "info", "R003",
            f"第 {run[0]}–{run[-1]} 页连续 {len(run)} 页非 Hero 版式："
            f"可考虑在中间插 1 页峰值页（参考 deck 同样存在连续谷底）。",
            run[0], {"pages": list(run), "length": len(run)}))

    run: List[int] = []
    for index, page in enumerate(pages, 1):
        if spec.is_hero(page):
            flush(run)
            run = []
            continue
        run.append(index)
    flush(run)


def _check_adjacent_layouts(report: Report, pages: Sequence["spec.Page"]) -> None:
    for index in range(1, len(pages)):
        here = _layout_key(pages[index].layout)
        prev = _layout_key(pages[index - 1].layout)
        if here and here == prev:
            report.add(Issue(
                "warn", "R004",
                f"第 {index} 页与第 {index + 1} 页版式相同（{here}）：请换成相邻的另一种版式。",
                index + 1, {"layout": here, "previous_page": index}))


# --------------------------------------------------------------------------- #
# PPTX checks
# --------------------------------------------------------------------------- #


@dataclass
class _ShapeInfo:
    """One measured shape, already converted into design px."""

    shape: Any = None
    kind: str = "shape"                 # shape | picture | table | chart | group | connector
    name: str = ""
    x: float = 0.0
    y: float = 0.0
    w: float = 0.0
    h: float = 0.0
    rect: Optional[Dict[str, float]] = None
    fill: Optional[str] = None          # #RRGGBB or None (no explicit fill)
    line: Optional[str] = None
    area: float = 0.0
    runs: List[Any] = dc_field(default_factory=list)     # _TextProbe
    max_px: float = 0.0
    has_text: bool = False


@dataclass
class _TextProbe:
    """One paragraph-and-run bundle with everything the linter needs."""

    text: str = ""
    size_pt: float = 0.0
    color: Optional[str] = None
    font: str = ""
    bold: bool = False
    italic: bool = False
    box: Dict[str, float] = dc_field(default_factory=dict)  # px

    @property
    def px(self) -> float:
        return self.size_pt / 0.75

    @property
    def weight(self) -> str:
        return "+".join(b for b, on in (("bold", self.bold), ("italic", self.italic)) if on) or "regular"


def _empty_stats() -> Dict[str, Any]:
    return {
        "pages": 0,
        "hero_pages": 0,
        "shapes": 0,
        "palette_colours": 0,
        "off_palette": 0,
        "brick_share": 0.0,
        "min_font_px": 0.0,
        "fonts": [],
        "error_count": 0,
        "warn_count": 0,
    }


def _finish_stats(stats: Dict[str, Any], report: Report) -> None:
    counts = report.counts()
    stats["error_count"] = counts["error"]
    stats["warn_count"] = counts["warn"]
    if isinstance(stats.get("off_palette"), list):
        stats["off_palette"] = len(stats["off_palette"])
    if isinstance(stats.get("fonts"), set):
        stats["fonts"] = sorted(stats["fonts"])
    stats.setdefault("brick_share", 0.0)
    stats.setdefault("min_font_px", 0.0)
    stats.setdefault("palette_colours", 0)


def check_pptx(target: Any, deck: Optional["spec.Deck"] = None) -> Report:
    """Run the geometry, typography and colour rules over a rendered deck.

    ``target`` is a filesystem path or an already-open ``pptx.Presentation``.
    ``deck`` is optional; when given it supplies the layouts (which is what the
    chrome rules need) and a nicer target label.
    """
    from pptx import Presentation  # local import: keeps check_deck import-light

    if isinstance(target, (str, bytes, os.PathLike)):
        path = os.fspath(target)
        try:
            prs = Presentation(path)
        except Exception as exc:  # pragma: no cover - environment dependent
            report = Report(target=str(path))
            report.add(Issue("error", "M004",
                             f"无法打开 PPTX 文件：{exc}", None, {"path": str(path)}))
            report.stats = _empty_stats()
            return report
        label = os.path.basename(str(path)) or str(path)
    else:
        prs = target
        label = (deck.source_path if deck and deck.source_path else None) or "Presentation"

    report = Report(target=label)
    stats = _empty_stats()

    scale = _scale_of(prs)
    slide_h = float(getattr(prs, "slide_height", 0) or 0) / 914400.0 * PX_PER_INCH
    canvas = _rect(0.0, 0.0, CANVAS_W, CANVAS_H) or {}

    slides = list(getattr(prs, "slides", []))
    stats["pages"] = len(slides)

    all_off: set = set()
    all_fonts: set = set()
    min_font = 0.0
    total_shapes = 0
    brick_areas = 0.0
    hero_pages = 0
    dark_pages: List[int] = []
    page_shapes: List[List[_ShapeInfo]] = []

    for index, slide in enumerate(slides, 1):
        layout = _layout_of(deck, index)
        hero = _is_hero_page(deck, index, layout)
        if hero:
            hero_pages += 1
        infos = _collect_shapes(slide, scale, slide_h)
        page_shapes.append(infos)
        total_shapes += len(infos)

        off, fonts, page_min, dark_share = _check_page_colour_and_type(
            report, infos, index, hero, layout)
        all_off |= off
        all_fonts |= fonts
        if page_min and (min_font == 0.0 or page_min < min_font):
            min_font = page_min
        brick_areas += _family_area(infos, BRICK_HEXES)
        if dark_share > DARK_SHARE_MAX:
            dark_pages.append(index)

        _check_geometry(report, infos, index, hero, layout)
        _check_anchor(report, infos, index, hero, layout)
        _check_charts(report, infos, index)

    # C005 has a deck-level half too: the guide caps dark cards at 3 per deck.
    if len(dark_pages) > MAX_DARK_CARDS:
        report.add(Issue(
            "info", "C005",
            f"全篇有 {len(dark_pages)} 页深色实底（第 "
            f"{'、'.join(str(i) for i in dark_pages)} 页），超过 3 张深色卡建议上限。",
            dark_pages[MAX_DARK_CARDS],
            {"pages": dark_pages, "max": MAX_DARK_CARDS}))

    stats["shapes"] = total_shapes
    stats["hero_pages"] = hero_pages
    stats["off_palette"] = sorted(all_off)
    stats["fonts"] = sorted(all_fonts)
    stats["min_font_px"] = round(min_font, 2)
    palette_keys = {colorlib.palette_key(h) for h in _drawn_hexes(page_shapes)}
    stats["palette_colours"] = len([k for k in palette_keys if k])
    canvas_area = _rect_area(canvas) * max(1, len(slides))
    stats["brick_share"] = round(brick_areas / canvas_area, 4) if canvas_area else 0.0

    report.sort()
    _finish_stats(stats, report)
    report.stats = stats
    return report


def _drawn_hexes(page_shapes: Sequence[Sequence[_ShapeInfo]]) -> List[str]:
    out: List[str] = []
    for infos in page_shapes:
        for info in infos:
            if info.fill:
                out.append(info.fill)
            for probe in info.runs:
                if probe.color:
                    out.append(probe.color)
    return out


def _family_area(infos: Sequence[_ShapeInfo], family: Iterable[str]) -> float:
    wanted = {h.upper() for h in family}
    return sum(info.area for info in infos if info.fill and info.fill.upper() in wanted)


def _scale_of(prs: Any) -> float:
    """``in -> design px`` factor, so 13.333in wide decks map 1:1 onto 1280."""
    try:
        width_in = float(prs.slide_width) / 914400.0
    except Exception:  # pragma: no cover - defensive
        return PX_PER_INCH
    if width_in <= 0:
        return PX_PER_INCH
    return CANVAS_W / width_in


def _layout_of(deck: Optional["spec.Deck"], index: int) -> str:
    if deck is None or index - 1 >= len(deck.pages):
        return ""
    return _layout_key(deck.pages[index - 1].layout)


def _is_hero_page(deck: Optional["spec.Deck"], index: int, layout: str) -> bool:
    if deck is not None and index - 1 < len(deck.pages):
        return bool(spec.is_hero(deck.pages[index - 1]))
    return layout in tokens.HERO_LAYOUTS


def _is_full_bleed(hero: bool, layout: str) -> bool:
    """Cover / closing pages may break every band (they draw their own chrome).

    When no deck is supplied the layout is unknown; a hero page is then treated
    as full bleed, which is the conservative reading of the guide.
    """
    if layout in FULL_BLEED_LAYOUTS:
        return True
    if layout:
        return False
    return hero


def _has_chrome(layout: str) -> bool:
    """True for pages that must respect every band (chrome + title + footer)."""
    if not layout:
        return True
    return bool(schema.LAYOUTS.get(layout, {}).get("chrome", False))


# --------------------------------------------------------------------------- #
# Shape collection
# --------------------------------------------------------------------------- #


def _collect_shapes(slide: Any, scale: float, slide_h: float) -> List[_ShapeInfo]:
    """Flatten one slide into measurable shapes, never raising."""
    out: List[_ShapeInfo] = []

    def visit(shape: Any, offset: Tuple[float, float] = (0.0, 0.0), depth: int = 0) -> None:
        if depth > 6:
            return
        try:
            info = _probe_shape(shape, scale, slide_h, offset)
        except Exception:
            return
        if info is not None:
            out.append(info)
        if getattr(info, "kind", "") == "group":
            try:
                children = list(shape.shapes)
            except Exception:
                children = []
            for child in children:
                visit(child, (info.x, info.y), depth + 1)

    try:
        shapes = list(slide.shapes)
    except Exception:  # pragma: no cover - defensive
        return out
    for shape in shapes:
        try:
            visit(shape)
        except Exception:  # pragma: no cover - defensive
            continue
    return out


def _probe_shape(shape: Any, scale: float, slide_h: float,
                 offset: Tuple[float, float]) -> Optional[_ShapeInfo]:
    try:
        left = shape.left
        top = shape.top
    except Exception:
        left = top = None
    if left is None or top is None:
        return None
    try:
        width = shape.width
        height = shape.height
    except Exception:
        width = height = None
    if width is None or height is None:
        return None

    x = float(left) / 914400.0 * scale + offset[0]
    y = float(top) / 914400.0 * scale + offset[1]
    w = float(width) / 914400.0 * scale
    h = float(height) / 914400.0 * scale

    info = _ShapeInfo(shape=shape, name=str(getattr(shape, "name", "") or ""),
                      x=x, y=y, w=w, h=h, rect=_rect(x, y, w, h))
    if info.rect is not None:
        info.area = _rect_area(info.rect)

    kind = _shape_kind(shape)
    info.kind = kind
    info.fill = _fill_hex(shape)
    info.line = _line_hex(shape)

    if kind == "chart":
        info.runs = _chart_text_probes(shape, info.rect)
        info.fill = info.fill or _chart_fill(shape)
    else:
        info.runs = _text_probes(shape, info.rect)
    info.has_text = bool(info.runs)
    info.max_px = max((r.px for r in info.runs), default=0.0)
    return info


def _shape_kind(shape: Any) -> str:
    name = type(shape).__name__.lower()
    if "group" in name:
        return "group"
    if "connector" in name:
        return "connector"
    if "picture" in name:
        return "picture"
    if "graphicframe" in name:
        try:
            if shape.has_chart:
                return "chart"
            if shape.has_table:
                return "table"
        except Exception:
            pass
        return "frame"
    if "chart" in name:
        return "chart"
    return "shape"


def _is_solid(fill: Any) -> bool:
    from pptx.enum.dml import MSO_FILL

    try:
        return fill.type == MSO_FILL.SOLID
    except Exception:
        return False


def _fill_hex(shape: Any) -> Optional[str]:
    """Explicit solid fill only — gradient / picture / inherited return ``None``."""
    try:
        fill = shape.fill
    except Exception:
        return None
    if not _is_solid(fill):
        return None
    try:
        return _hex_of(fill.fore_color.rgb)
    except Exception:
        return None


def _line_hex(shape: Any) -> Optional[str]:
    try:
        line = shape.line
        if not _is_solid(line.fill):
            return None
        return _hex_of(line.color.rgb)
    except Exception:
        return None


def _chart_fill(shape: Any) -> Optional[str]:
    """A chart's background fill, when it declares one."""
    try:
        chart = shape.chart
        if chart is None:
            return None
        from pptx.oxml.ns import qn

        sp_pr = chart._chartSpace.find(qn("c:spPr"))
        if sp_pr is None:
            return None
        srgb = sp_pr.find(".//" + qn("a:srgbClr"))
        if srgb is not None:
            return _hex_of(srgb.get("val"))
    except Exception:
        return None
    return None


# --------------------------------------------------------------------------- #
# Text probing
# --------------------------------------------------------------------------- #


def _text_probes(shape: Any, box: Optional[Dict[str, float]]) -> List[_TextProbe]:
    probes: List[_TextProbe] = []
    try:
        if not shape.has_text_frame:
            return probes
        text_frame = shape.text_frame
    except Exception:
        return probes

    default_pt = _default_size_pt(text_frame)
    for para in list(getattr(text_frame, "paragraphs", [])):
        runs = list(getattr(para, "runs", []))
        if not runs:
            continue
        para_text = "".join(_clean_text(r.text) for r in runs)
        if not para_text:
            continue
        for run in runs:
            text = _clean_text(run.text)
            if not text:
                continue
            font = run.font
            size_pt = None
            try:
                if font.size is not None:
                    size_pt = float(font.size.pt)
            except Exception:
                size_pt = None
            if size_pt is None:
                size_pt = default_pt
            if not size_pt:
                continue
            probes.append(_TextProbe(
                text=text,
                size_pt=size_pt,
                color=_font_color(run),
                font=str(getattr(font, "name", "") or ""),
                bold=bool(getattr(font, "bold", False)),
                italic=bool(getattr(font, "italic", False)),
                box=dict(box or {}),
            ))
    return probes


def _default_size_pt(text_frame: Any) -> float:
    """Fallback size from the ``defRPr`` the generator wrote, if any."""
    try:
        element = text_frame._txBody.find(".//{http://schemas.openxmlformats.org/drawingml/2006/main}defRPr")
        if element is not None and element.get("sz"):
            return float(element.get("sz")) / 100.0
    except Exception:
        pass
    return 0.0


def _font_color(run: Any) -> Optional[str]:
    try:
        return _hex_of(run.font.color.rgb)
    except Exception:
        return None


def _d_lbls_of(obj: Any) -> Any:
    """The ``<c:dLbls>`` element behind a plot / series / raw XML element.

    Accepts a python-pptx wrapper (``plot``, ``series.data_labels``) **and** a
    bare lxml element (``series._element``), which is the only way to inspect a
    series without triggering python-pptx's create-on-read
    ``Series.data_labels`` property.
    """
    from pptx.oxml.ns import qn

    if obj is None:
        return None
    element = getattr(obj, "_element", None)
    if element is None:
        element = getattr(obj, "_dLbls", None)
    if element is None:
        element = obj                     # already an lxml element
    if not hasattr(element, "tag"):
        return None
    if element.tag == qn("c:dLbls"):
        return element
    return element.find(qn("c:dLbls"))


def _labels_disabled(element: Any) -> bool:
    """True only when the XML positively says "no data labels".

    A series with no ``<c:dLbls>`` inherits the (enabled) PowerPoint default, so
    an absent element is *not* reported — the linter stays conservative and only
    flags a chart that turned labels off.
    """
    if element is None:
        return False
    from pptx.oxml.ns import qn

    delete = element.find(qn("c:delete"))
    if delete is not None and delete.get("val") not in (None, "0", "false"):
        return True
    flags = ("c:showVal", "c:showCatName", "c:showSerName", "c:showPercent", "c:showLegendKey")
    seen = [element.find(qn(name)) for name in flags]
    seen = [el for el in seen if el is not None]
    if not seen:
        return False
    return all(el.get("val") in ("0", "false") for el in seen)


def _labels_deleted(element: Any) -> bool:
    """True only for an explicit ``<c:delete val="1"/>`` (labels switched off)."""
    if element is None:
        return False
    from pptx.oxml.ns import qn

    delete = element.find(qn("c:delete"))
    return delete is not None and str(delete.get("val")) not in ("0", "false", "None")


def _chart_text_probes(shape: Any, box: Optional[Dict[str, float]]) -> List[_TextProbe]:
    """Data labels, axis titles and the chart title, as text probes."""
    probes: List[_TextProbe] = []
    try:
        chart = shape.chart
    except Exception:
        return probes

    def from_tx_pr(tx_pr: Any) -> None:
        if tx_pr is None:
            return
        try:
            for para in tx_pr.paragraphs:
                for run in para.runs:
                    text = _clean_text(run.text)
                    if not text:
                        continue
                    size = run.font.size
                    probes.append(_TextProbe(
                        text=text,
                        size_pt=float(size.pt) if size is not None else 0.0,
                        color=_font_color(run),
                        font=str(run.font.name or ""),
                        bold=bool(run.font.bold),
                        box=dict(box or {}),
                    ))
        except Exception:
            return

    try:
        if chart.has_title:
            from_tx_pr(chart.chart_title.text_frame)
    except Exception:
        pass
    for getter in ("category_axis", "value_axis"):
        try:
            axis = getattr(chart, getter)
            if axis.has_title:
                from_tx_pr(axis.axis_title.text_frame)
        except Exception:
            continue
    try:
        plots = list(chart.plots)
    except Exception:
        plots = []
    for plot in plots:
        for series in list(getattr(plot, "series", [])):
            try:
                if _d_lbls_of(series.data_labels) is None:
                    continue
                from_tx_pr(series.data_labels.text_frame)
            except Exception:
                continue
    return [p for p in probes if p.size_pt > 0]


# --------------------------------------------------------------------------- #
# Per-page rules
# --------------------------------------------------------------------------- #


def _check_geometry(report: Report, infos: Sequence[_ShapeInfo], index: int,
                    hero: bool, layout: str) -> None:
    full_bleed = _is_full_bleed(hero, layout)
    canvas = _rect(0.0, 0.0, CANVAS_W, CANVAS_H) or {}
    reach = 0.0
    has_content = False

    for info in infos:
        rect = info.rect
        if rect is None:
            continue

        # -- M001 safe side margin ---------------------------------------- #
        # Exempt full-bleed chrome (top bar / bottom band / background) and the
        # band-A ornament strip, which the guide itself places at x=32.
        bleeds = (full_bleed or info.x <= 0.0 or info.w >= CANVAS_W
                  or _is_top_bar_ornament(info))
        if not bleeds and (info.x < SAFE_X - 1.0 or rect["right"] > SAFE_RIGHT + 1.0):
            side = "左" if info.x < SAFE_X else "右"
            report.add(Issue(
                "error", "M001",
                f"元素突破{side}侧 40px 安全边距（x={_fmt_px(info.x)}, "
                f"右边界={_fmt_px(rect['right'])}）：请收进 40–1240 的可用宽度。",
                index, {"name": info.name, "x": round(info.x, 1),
                        "right": round(rect["right"], 1)}))

        # -- M004 past the canvas ----------------------------------------- #
        if not _inside(canvas, rect, tol=1.0):
            report.add(Issue(
                "info", "M004",
                f"元素超出 1280×720 画布（x={_fmt_px(info.x)}, y={_fmt_px(info.y)}, "
                f"右={_fmt_px(rect['right'])}, 下={_fmt_px(rect['bottom'])}）。",
                index, {"name": info.name, "right": round(rect["right"], 1),
                        "bottom": round(rect["bottom"], 1)}))

        if info.kind in ("chart", "table", "picture") or info.has_text:
            has_content = True
        if CONTENT_TOP - 1.0 <= info.y <= CONTENT_BOTTOM + 1.0 or info.has_text:
            reach = max(reach, rect["bottom"])

    # -- M002 the reserved strip under the top bar ------------------------- #
    if not full_bleed:
        strip = _rect(0.0, CHROME_TOP_BAR_H, CANVAS_W,
                      CHROME_RESERVED_BOTTOM - CHROME_TOP_BAR_H)
        for info in infos:
            rect = info.rect
            if rect is None or strip is None:
                continue
            if info.h >= CANVAS_H * 0.9:      # full-page background, not content
                continue
            if _overlaps(rect, strip):
                overlap = _intersect(rect, strip)
                report.add(Issue(
                    "error", "M002",
                    f"元素压到顶条预留区 y60–72（y={_fmt_px(info.y)}，高 {_fmt_px(info.h)}）："
                    f"请下移到 y≥72 的标题区。",
                    index, {"name": info.name, "y": round(info.y, 1),
                            "overlap_px2": round(overlap, 1)}))

    # -- M003 content pages must fill the canvas --------------------------- #
    if _has_chrome(layout) and not full_bleed:
        if has_content and reach < FILL_TARGET_Y:
            report.add(Issue(
                "warn", "M003",
                f"内容没有撑满：最低元素只到 y={_fmt_px(reach)}（要求 ≥600），"
                f"卡片填充率应 ≥80%。",
                index, {"max_bottom": round(reach, 1), "target": FILL_TARGET_Y}))


def _check_anchor(report: Report, infos: Sequence[_ShapeInfo], index: int,
                  hero: bool, layout: str) -> None:
    if not _has_chrome(layout):
        return
    biggest_text = max((i.max_px for i in infos), default=0.0)
    band = _rect(SAFE_X, CONTENT_TOP, CANVAS_W - 2 * SAFE_X, CONTENT_BOTTOM - CONTENT_TOP)
    band_area = _rect_area(band) if band else 1.0
    biggest_shape = 0.0
    for info in infos:
        if info.rect is None or not band:
            continue
        biggest_shape = max(biggest_shape, _intersect(info.rect, band))
    share = biggest_shape / band_area if band_area else 0.0
    if biggest_text < MIN_ANCHOR_PX and share < ANCHOR_AREA_SHARE:
        report.add(Issue(
            "info", "A001",
            f"缺少视觉锚点：最大文字 {_fmt_px(biggest_text)}px（要求 ≥44px），"
            f"最大图形占内容区 {_fmt_share(share)}（要求 ≥40%）。",
            index, {"max_text_px": round(biggest_text, 1), "max_shape_share": round(share, 3)}))


def _check_colour(report: Report, hexv: str, where: str, index: int,
                  area: float = 0.0) -> None:
    reason = colorlib.forbidden_reason(hexv)
    if reason:
        report.add(Issue(
            "error", "C002",
            f"{where}使用了禁用颜色 {hexv}（{reason}）：请改用调色板中的色值。",
            index, {"hex": hexv, "reason": reason, "area_px2": round(area, 1)}))
        return
    if not colorlib.is_allowed(hexv):
        key, dist = _nearest_palette(hexv)
        hint = f"，最接近调色板 {key}（距离 {dist:.0f}）" if key and dist is not None and dist <= 30 else ""
        report.add(Issue(
            "error", "C001",
            f"{where}使用了调色板外的颜色 {hexv}{hint}：请改用 tokens.PALETTE 中的颜色。",
            index, {"hex": hexv, "nearest": key, "distance": None if dist is None else round(dist, 1),
                    "area_px2": round(area, 1)}))


def _background_for(info: _ShapeInfo, infos: Sequence[_ShapeInfo]) -> str:
    """Best guess at the colour behind a text box: deepest overlapping fill."""
    if info.fill:
        return info.fill
    rect = info.rect
    if rect is None:
        return "#FFFFFF"
    area = _rect_area(rect)
    best_parent: Optional[_ShapeInfo] = None
    best_contain = 0.0
    best_overlap = 0.0
    best_overlap_info: Optional[_ShapeInfo] = None
    for other in infos:
        if other is info or other.fill is None or other.rect is None:
            continue
        if other.has_text:
            continue
        overlap = _intersect(rect, other.rect)
        if overlap <= 0:
            continue
        if _inside(other.rect, rect, tol=1.0) and _rect_area(other.rect) > best_contain:
            best_parent, best_contain = other, _rect_area(other.rect)
        if overlap > best_overlap:
            best_overlap, best_overlap_info = overlap, other
    if best_parent is not None:
        return best_parent.fill or "#FFFFFF"
    if best_overlap_info is not None and best_overlap >= 0.5 * area:
        return best_overlap_info.fill or "#FFFFFF"
    return "#FFFFFF"


def _check_page_colour_and_type(report: Report, infos: Sequence[_ShapeInfo], index: int,
                                hero: bool, layout: str
                                ) -> Tuple[set, set, float, float]:
    """Colour rules (C001–C005, K001) and type rules (T001–T005) for one page.

    Returns ``(off_palette_hexes, font_families, smallest_font_px, dark_share)``.
    """
    off_palette: set = set()
    fonts: set = set()
    min_font = 0.0
    page_area = CANVAS_W * CANVAS_H

    # -- fills ------------------------------------------------------------- #
    brick_area = 0.0
    tint_area = 0.0
    accent_tint_area = 0.0
    dark_area = 0.0
    reported: set = set()
    contrast_seen: set = set()

    def report_colour(hexv: str, where: str, area: float = 0.0) -> None:
        """Report each distinct colour once per surface kind: keeps output readable."""
        surface = where.rsplit("的", 1)[-1]
        key = (hexv, surface)
        if key in reported:
            return
        reported.add(key)
        _check_colour(report, hexv, where, index, area)

    for info in infos:
        if info.fill:
            report_colour(info.fill, f"图形 {info.name!r} 的填充", info.area)
            if not colorlib.is_allowed(info.fill):
                off_palette.add(info.fill)
            upper = info.fill.upper()
            if upper in BRICK_HEXES:
                brick_area += info.area
            if upper in TINT_HEXES:
                tint_area += info.area
            if upper in ACCENT_TINT_HEXES:
                accent_tint_area += info.area
            if upper in DARK_HEXES:
                dark_area += info.area
        if info.line:
            report_colour(info.line, f"图形 {info.name!r} 的描边", 0.0)
            if not colorlib.is_allowed(info.line):
                off_palette.add(info.line)

    # -- text colour, contrast, minimum size ------------------------------- #
    weights: set = set()
    for info in infos:
        for probe in info.runs:
            fonts.add(probe.font or "(默认)")
            weights.add(probe.weight)
            px = probe.px
            if px > 0 and (min_font == 0.0 or px < min_font):
                min_font = px
            if 0 < px < MIN_PX_ANY - 0.01:
                report.add(Issue(
                    "error", "T001",
                    f"文字只有 {_fmt_px(px)}px（下限 11px）：请改用 caption / table_cell 等更大字号。",
                    index, {"px": round(px, 2), "text": probe.text[:60], "name": info.name}))
            elif px and px < MIN_PX_BODY - 0.01:
                # 11–13px is the auxiliary tier (caption 11.5 / footer 12 / kpi label 12),
                # so only *running body copy* is a violation: long, prose-like, in the
                # content band, and actually wrapping to two or more lines in its own box.
                if _is_running_body(probe):
                    report.add(Issue(
                        "error", "T002",
                        f"正文只有 {_fmt_px(px)}px（下限 13px）：请改用 card_body 及以上字号。",
                        index, {"px": round(px, 2), "text": probe.text[:60], "name": info.name,
                                "lines": _probe_lines(probe)}))
            if probe.color:
                report_colour(probe.color, f"文字 {probe.text[:20]!r} 的颜色", 0.0)
                if not colorlib.is_allowed(probe.color):
                    off_palette.add(probe.color)
                background = _background_for(info, infos)
                try:
                    ratio = colorlib.contrast_ratio(probe.color, background)
                except Exception:
                    ratio = MIN_CONTRAST
                limit = LARGE_TYPE_CONTRAST if px >= LARGE_TYPE_PX else MIN_CONTRAST
                if ratio < limit:
                    pair = (probe.color.upper(), background.upper())
                    if probe.color.upper() == background.upper():
                        continue        # background probe failed; cannot judge
                    if pair in contrast_seen:
                        continue                       # one report per page and pair
                    contrast_seen.add(pair)
                    # The palette's own auxiliary hues (teal / grayblue / faint) are
                    # sub-AA on light grounds by construction and the guide sanctions
                    # them for辅助与展示层级: report once, as info, with the reason.
                    if pair in DOCUMENTED_LOW_CONTRAST:
                        report.add(Issue(
                            "info", "K001",
                            f"对比度 {ratio:.2f}:1（AA 需 {limit:g}:1）：{probe.color} 压在 {background} 上；"
                            f"该组合属色板固有（见 docs/STYLE.md §2.3），仅限辅助 / 展示层级使用。",
                            index, {"fg": probe.color, "bg": background, "ratio": ratio,
                                    "px": round(px, 2), "name": info.name,
                                    "documented": True}))
                    else:
                        report.add(Issue(
                            "warn", "K001",
                            f"文字对比度只有 {ratio:.2f}:1（要求 ≥{limit:g}:1）："
                            f"{probe.color} 压在 {background} 上，请调整文字或底色。",
                            index, {"fg": probe.color, "bg": background, "ratio": ratio,
                                    "px": round(px, 2), "name": info.name}))

            _check_overflow(report, probe, info, index)

    if len(fonts) > MAX_FAMILIES:
        report.add(Issue(
            "warn", "T003",
            f"本页用了 {len(fonts)} 套字体家族（上限 2）：{'、'.join(sorted(fonts))}，请统一字族。",
            index, {"fonts": sorted(fonts), "max": MAX_FAMILIES}))
    if len(weights) > MAX_WEIGHTS:
        report.add(Issue(
            "warn", "T004",
            f"本页用了 {len(weights)} 级字重（上限 2）：{'、'.join(sorted(weights))}，请只保留 Bold + Regular。",
            index, {"weights": sorted(weights), "max": MAX_WEIGHTS}))
    if brick_area / page_area > BRICK_SHARE_MAX:
        report.add(Issue(
            "warn", "C003",
            f"砖红警示（#C0392B）占页面 {_fmt_share(brick_area / page_area)}，超过 6% 上限："
            f"请减少红色文字与红色描边。",
            index, {"share": round(brick_area / page_area, 4), "max": BRICK_SHARE_MAX}))
    # Accent tints (mint / pink) carry the guide's 0–20% budget.  The plain grey
    # card surface (#F4F7FB) is *not* budgeted the same way: cards are supposed to
    # fill the content band, which alone exceeds 20% on any "撑满" page — see
    # docs/STYLE.md §9 (reconciliation of the 0–20% line with "卡片撑满").
    if accent_tint_area / page_area > TINT_SHARE_MAX:
        report.add(Issue(
            "warn", "C004",
            f"浅青/浅红强调底色占页面 {_fmt_share(accent_tint_area / page_area)}，超过 20%："
            f"请缩小强调色卡面积。",
            index, {"share": round(accent_tint_area / page_area, 4), "max": TINT_SHARE_MAX,
                    "grey_surface_share": round(tint_area / page_area, 4)}))
    if dark_area / page_area > DARK_SHARE_MAX:
        report.add(Issue(
            "info", "C005",
            f"深色实底占页面 {_fmt_share(dark_area / page_area)}，超过 40%："
            f"全篇深色卡建议不超过 3 张。",
            index, {"share": round(dark_area / page_area, 4), "max": DARK_SHARE_MAX}))
    return off_palette, fonts, min_font, dark_area / page_area


def _is_body_like(probe: _TextProbe) -> bool:
    """Heuristic: long, punctuation-bearing, non-numeric text is body copy."""
    text = probe.text.strip()
    if len(text) < 24:
        return False
    digits = sum(1 for ch in text if ch.isdigit())
    if digits > len(text) * 0.5:
        return False
    return True


def _probe_lines(probe: _TextProbe) -> int:
    """Estimated line count of a probe inside its own text box."""
    width = float(probe.box.get("w") or 0.0)
    if width <= 0:
        return 1
    try:
        return primitives.line_count(probe.text, max(1.0, probe.px), width, probe.bold)
    except Exception:  # pragma: no cover - defensive
        return 1


def _is_running_body(probe: _TextProbe) -> bool:
    """True only for genuine running body copy under the 13px floor.

    A caption, a footer, a source note or a one-line figure note is legitimate
    at 11–13px (the type scale defines those tokens); running prose that wraps
    to two or more lines is not.
    """
    text = probe.text.strip()
    if len(text) < 30 or not _is_body_like(probe):
        return False
    if float(probe.box.get("y") or 0.0) >= FOOTER_BAND_Y:
        return False                                    # footer / source / page number
    return _probe_lines(probe) >= 2


def _check_overflow(report: Report, probe: _TextProbe, info: _ShapeInfo, index: int) -> None:
    box = probe.box
    if not box or box.get("w", 0) <= 0 or box.get("h", 0) <= 0:
        return
    try:
        lines = primitives.wrap_lines(probe.text, probe.px, box["w"], probe.bold)
        needed = len(lines) * probe.px * 1.5
    except Exception:
        return
    if box["h"] < 1:
        return
    if needed > box["h"] * OVERFLOW_SLACK:
        report.add(Issue(
            "warn", "T005",
            f"文字预估溢出：{len(lines)} 行约 {_fmt_px(needed)}px，超过文本框 {_fmt_px(box['h'])}px 的 15%。",
            index, {"name": info.name, "lines": len(lines), "needed_px": round(needed, 1),
                    "box_h": round(box["h"], 1), "text": probe.text[:60]}))


# --------------------------------------------------------------------------- #
# Chart rules
# --------------------------------------------------------------------------- #


def _check_charts(report: Report, infos: Sequence[_ShapeInfo], index: int) -> None:
    for info in infos:
        if info.kind == "chart":
            _check_chart(report, info, index)
        elif info.kind == "table":
            _check_table(report, info, index)


def _check_chart(report: Report, info: _ShapeInfo, index: int) -> None:
    """H001 data labels + H002 explicit height, plus an equal-width row probe."""
    try:
        chart = info.shape.chart
    except Exception:
        return

    # -- H002: an explicit, non-zero height -------------------------------- #
    height_emu = 0
    try:
        height_emu = int(info.shape.height or 0)
    except Exception:
        height_emu = 0
    if not height_emu or info.h <= 1.0:
        report.add(Issue(
            "error", "H002",
            f"图表 {info.name!r} 没有高度（{_fmt_px(info.h)}px）：图表必须显式给出高度。",
            index, {"name": info.name, "height_px": round(info.h, 1)}))

    # -- H001: data labels, per plot then per series ------------------------ #
    try:
        plots = list(chart.plots)
    except Exception:
        plots = []
    unlabelled: List[str] = []
    for plot in plots:
        plot_element = _d_lbls_of(plot)
        if _labels_disabled(plot_element):
            # Chart-level "no data labels": every series inherits it.
            names = [str(getattr(s, "name", "") or "未命名序列") for s in list(getattr(plot, "series", []))]
            unlabelled.extend(names or ["未命名序列"])
            continue
        for series in list(getattr(plot, "series", [])):
            # Only an explicit <c:delete val="1"/> counts.  Reading
            # ``series.data_labels`` would create an all-off <c:dLbls/> and the
            # linter would then flag its own edit (and `_chart_text_probes` walks
            # the same chart earlier in the run), so a bare all-zero element is
            # treated as "no opinion, inherits the chart setting".
            element = _d_lbls_of(getattr(series, "_element", None))
            if _labels_deleted(element):
                unlabelled.append(str(getattr(series, "name", "") or "未命名序列"))
    if unlabelled:
        report.add(Issue(
            "warn", "H001",
            f"图表 {info.name!r} 的 {'、'.join(unlabelled)} 未开启数据标签：请打开“显示值”。",
            index, {"name": info.name, "series": unlabelled}))

    # -- equal-width card row (R005), conservative -------------------------- #
    try:
        cols = len(list(chart.plots[0].categories))
    except Exception:
        cols = 0
    if cols >= 3:
        report.add(Issue(
            "info", "R005",
            f"图表 {info.name!r} 为 {cols} 类目等宽柱：如需横向并排展示，请注意全篇等宽卡片 ≤2 页。",
            index, {"name": info.name, "categories": cols}))


def _check_table(report: Report, info: _ShapeInfo, index: int) -> None:
    """Tables keep the palette honest: cells inherit, headers must be navy."""
    try:
        table = info.shape.table
    except Exception:
        return
    try:
        header_fill = _hex_of(table.rows[0].cells[0].fill.fore_color.rgb)
    except Exception:
        header_fill = None
    if header_fill:
        _check_colour(report, header_fill, "表头底色", index, 0.0)


# --------------------------------------------------------------------------- #
# Dispatch
# --------------------------------------------------------------------------- #


def check(target: Any, deck: Optional["spec.Deck"] = None) -> Report:
    """Dispatch on the target: ``.pptx`` -> :func:`check_pptx`, else document.

    ``.yaml`` / ``.yml`` / ``.json`` are loaded through :mod:`deepocean.spec`
    and checked statically.  A ``spec.Deck`` or ``pptx.Presentation`` instance
    is accepted directly as well.
    """
    if isinstance(target, spec.Deck):
        return check_deck(target)
    if hasattr(target, "slides") and hasattr(target, "slide_width"):
        return check_pptx(target, deck)

    path = os.fspath(target)
    suffix = os.path.splitext(str(path))[1].lower()
    if suffix == ".pptx":
        return check_pptx(path, deck)
    if suffix in (".yaml", ".yml", ".json"):
        return check_deck(spec.Deck.load(path))
    try:
        return check_pptx(path, deck)
    except Exception:
        return check_deck(spec.Deck.load(path))


def _deck_target(deck: "spec.Deck") -> str:
    if deck.source_path:
        return os.path.basename(deck.source_path)
    title = str(deck.meta.title or "").strip()
    return title or "deck"


# --------------------------------------------------------------------------- #
# Documentation helper
# --------------------------------------------------------------------------- #


def rule_table() -> str:
    """The whole rule set as a Markdown table (``code | level | rule | guide``)."""
    lines = [
        "| code | level | rule | guide section |",
        "| --- | --- | --- | --- |",
    ]
    for code in sorted(RULE_CODES, key=lambda c: _CODE_ORDER.get(c, 999_999)):
        level, rule, section = _RULE_META.get(code, ("warn", RULE_CODES[code], "09 · CHECKLIST"))
        lines.append(f"| `{code}` | {level} | {rule} | {section} |")
    return "\n".join(lines)
