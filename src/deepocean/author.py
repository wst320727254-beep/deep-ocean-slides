# -*- coding: utf-8 -*-
"""Digest -> deck.

Two authoring paths, deliberately separated:

``skeleton_deck(digest)``
    Offline and deterministic.  It drafts a full deck from what was *found* in
    the paper — section text becomes bullets, extracted numbers become the chart
    and the banner, the best figure becomes an evidence page.  It never invents
    a sentence or a digit: every block carries the page it came from.

``llm_deck(digest, ...)``
    Hands the digest to an OpenAI-compatible chat model and asks for a deck
    document in the repo's own schema, then validates it (and retries once with
    the validation errors appended when the model colours outside the lines).

Both paths return a plain ``dict`` ready for :meth:`deepocean.spec.Deck.from_dict`.
The layout rhythm follows the style guide: cover -> background -> questions ->
method -> results -> evidence -> findings -> closing, one peak every 2-3 pages.
"""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional, Sequence, Tuple

from . import schema, spec, tokens
from .paper import Digest, Section

MAX_DECK_PAGES = 13
MAX_FIGURE_PAGES = 2          # "图片不需要太多" — one figure page is usually enough

DEFAULT_BASE_URL = "https://api.deepseek.com/v1"
DEFAULT_MODEL = "deepseek-chat"
API_KEY_ENV = ("DEEPSEEK_API_KEY", "OPENAI_API_KEY", "DEEP_OCEAN_API_KEY")

#: Chinese card titles for the extracted section keys (the heading itself is
#: usually "1. Introduction", which belongs in the English subtitle, not as a
#: Chinese card title).
SECTION_LABEL: Dict[str, str] = {
    "abstract": "摘要要点",
    "introduction": "引言要点",
    "related": "相关工作",
    "theory": "理论与假设",
    "method": "方法与数据",
    "results": "主要结果",
    "mechanism": "机制检验",
    "discussion": "讨论",
    "conclusion": "结论与展望",
}


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #


def _clean(text: str, limit: int = 120) -> str:
    """Shorten text on a word/sentence boundary — never mid-word.

    Extracted PDF text is full of long English sentences; cutting at exactly
    ``limit`` characters produced slides that read ``"w/…"`` and ``"interactio…"``.
    """
    text = " ".join(str(text or "").split())
    if len(text) <= limit:
        return text
    window = text[:limit]
    for mark in ("。", "！", "？", "；", ". ", "! ", "? ", "; ", "，", ",", " "):
        cut = window.rfind(mark)
        if cut >= max(8, limit // 2):
            return window[:cut].rstrip(" ，,、；;:：") + "…"
    return window.rstrip() + "…"


def _usable_table(table: Dict[str, Any]) -> Optional[List[List[str]]]:
    """Only keep an auto-extracted table when it actually looks like a table.

    Rows of flowing prose that happen to contain two spaces produced tables full
    of fragments; a table page is worth showing only if the grid is consistent,
    mostly filled and carries numbers.
    """
    rows: List[List[str]] = []
    for line in str(table.get("text", "")).splitlines():
        cells = [cell.strip() for cell in line.split("|")]
        if any(cells):
            rows.append(cells)
    if len(rows) < 3:
        return None
    widths = {len(row) for row in rows}
    if max(widths) - min(widths) > 1:
        return None
    flat = [cell for row in rows for cell in row]
    if sum(1 for cell in flat if cell) / max(1, len(flat)) < 0.75:
        return None
    if sum(1 for cell in flat if re.search(r"\d", cell)) < 2:
        return None
    width = max(widths)
    return [row + [""] * (width - len(row)) for row in rows[:6]]


def _percent_value(value: str) -> Optional[float]:
    """``"-33.4%"`` / ``"−33.4 %"`` -> ``-33.4`` (typeset papers use U+2212)."""
    match = re.fullmatch(r"\s*([+\-−–]?\d+(?:\.\d+)?)\s*%\s*", value)
    if not match:
        return None
    return float(match.group(1).replace("−", "-").replace("–", "-"))


def _bullets(section: Optional[Section], limit: int = 4, width: int = 88) -> List[str]:
    return section.bullets(limit=limit, width=width) if section else []


def _number_sentence(numbers: Sequence[Dict[str, Any]]) -> str:
    """A real sentence built from an extracted number, used when prose runs out."""
    if not numbers:
        return "自动提取有限，请对照原文结果章节补一句结论。"
    top = numbers[0]
    return f"{top['value']} —— {top['context']}（p{top['page']}）"


def _source_note(digest: Digest, page: Optional[int] = None) -> str:
    bits = [os.path.basename(digest.path)]
    if digest.year:
        bits.append(digest.year)
    if page:
        bits.append(f"p{page}")
    return " · ".join(bits)


def _chart_label(context: str, value: str, limit: int = 16) -> str:
    """A short axis label for one extracted number.

    The raw context is a sentence fragment ("Customers only increase their
    searches (10% increase) in…").  For an axis we want the phrase that *names*
    the number, so we take the clause before it, strip brackets and trailing
    values, and trim — never leaving a dangling "increase) in".
    """
    text = " ".join(str(context or "").split())
    position = text.find(value)
    if position <= 0:
        return _clean(_tidy_label(text), limit)

    before = text[:position].rstrip()
    clause = re.split(r"[;；。(（]", before)[-1].strip()
    after = text[position + len(value):].lstrip(" ;；,，、)）")
    tail = re.split(r"[;；。]|\.\s", after)[0].strip()

    clause = _tidy_label(clause)
    tail = _tidy_label(tail)
    candidate = clause if len(clause) >= 8 else (tail or clause)
    if len(candidate) < 4:
        candidate = _tidy_label(text)
    if len(candidate) < 3:
        candidate = text
    return _clean(candidate, limit)


def _tidy_label(text: str) -> str:
    """Drop brackets and dangling punctuation from a label fragment."""
    cleaned = re.sub(r"[()（）\[\]【】]", " ", str(text or ""))
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" ,;；.·-—…")
    return cleaned


def _chart_from_numbers(digest: Digest, max_series: int = 6) -> Optional[Dict[str, Any]]:
    """A bar chart of the extracted percentages, labelled by their context.

    Only numbers that score as *this paper's results* are eligible: quoting a
    percentage from the literature review on the results slide is how a real
    number still produces a wrong chart.
    """
    points: List[Tuple[str, float, int]] = []
    for item in digest.top_numbers(24, min_score=2):
        if item["kind"] != "percent":
            continue
        value_num = _percent_value(item["value"])
        if value_num is None or abs(value_num) > 500:
            continue
        label = _chart_label(item["context"], item["value"])
        if any(label == existing[0] for existing in points):
            continue
        points.append((label, value_num, item["page"]))
        if len(points) >= max_series:
            break
    if len(points) < 2:
        return None
    return {
        "type": "bar",
        "title": "论文中提取到的百分比（横轴为原文上下文）",
        "categories": [p[0] for p in points],
        "series": [{"name": "原文数值 (%)", "values": [p[1] for p in points],
                    "color": "navy" if points[0][1] < 0 else "teal"}],
        "unit": "%",
        "height": 320,
        "note": "数值由 PDF 文本直接提取，请回原页核对：" +
                "、".join(f"p{p[2]}" for p in points[:4]),
    }


def _route(digest: Digest) -> List[str]:
    """The page plan: which layouts this paper's content can actually fill."""
    plan = ["cover", "two_column"]
    if _bullets(digest.section("method")):
        plan.append("roadmap")
    elif _bullets(digest.section("theory")):
        plan.append("big_number")
    if _chart_from_numbers(digest):
        plan.append("chart_insight")
    if digest.best_figures(1):
        plan.append("image_evidence")
    if digest.tables:
        plan.append("data_table")
    plan += ["key_findings", "closing"]
    return plan[:MAX_DECK_PAGES]


# --------------------------------------------------------------------------- #
# offline skeleton
# --------------------------------------------------------------------------- #


def skeleton_deck(digest: Digest, *, journal: str = "", kicker: str = "组会文献汇报",
                  max_figures: int = 1, author: str = "") -> Dict[str, Any]:
    """Draft a complete deck from the digest alone (no model, no invention)."""
    max_figures = max(0, min(MAX_FIGURE_PAGES, max_figures))
    title = _clean(digest.title, 60) or os.path.splitext(os.path.basename(digest.path))[0]
    abstract = digest.section("abstract")
    intro = digest.section("introduction")
    method = digest.section("method")
    results = digest.section("results") or digest.section("mechanism")
    discussion = digest.section("discussion")
    conclusion = digest.section("conclusion")
    numbers = digest.top_numbers(6)
    chart = _chart_from_numbers(digest)

    pages: List[Dict[str, Any]] = []

    # 01 cover ------------------------------------------------------------ #
    pages.append({
        "layout": "cover",
        "title": title,
        "data": {
            "english_title": _clean(digest.title, 90) if re.search(r"[A-Za-z]", digest.title) else "",
            "authors": author or "、".join(digest.authors[:3]) or "汇报人",
            "affiliation": "文献组会 · " + (digest.year or "—"),
            "series": journal or digest.year or "",
            "note": f"PDF {digest.pages} 页 · 提取到 {len(digest.numbers)} 处数字、"
                    f"{len(digest.tables)} 个候选表格、{len(digest.figures)} 张候选配图",
            "band": _source_note(digest),
        },
    })

    # 02 background ------------------------------------------------------- #
    lead = abstract or intro
    right: List[Dict[str, Any]] = []
    for label, section in (("研究问题", intro), ("方法", method), ("数据", method)):
        bullets = _bullets(section, limit=2, width=42)
        if bullets:
            right.append({"chip": label, "title": _clean(section.heading if section else label, 16),
                          "body": bullets[0], "tone": "tint" if len(right) == 0 else "plain"})
    for item in numbers[:1]:
        right.append({"title": f"原文关键数字：{item['value']}", "body": _clean(item["context"], 60),
                      "tone": "primary"})
    pages.append({
        "layout": "two_column",
        "kicker": "01 · BACKGROUND",
        "title": "研究背景",
        "subtitle": _clean(lead.heading if lead else "论文摘要与引言", 40),
        "data": {
            "ratio": 0.60,
            "left": {
                "title": SECTION_LABEL.get(lead.key, "原文要点") if lead else "原文要点",
                "body": _bullets(lead, limit=1, width=150)[0] if _bullets(lead, 1, 150) else "（原文摘要较短，请人工补一句背景。）",
                "items": _bullets(lead, limit=4) or _bullets(intro, limit=4),
                "footer": f"原文页码：p{lead.page}" if lead else "",
            },
            "right": right or [{"title": "要点", "body": "原文结构化信息不足，请人工补充。", "tone": "plain"}],
        },
    })

    # 03 questions / method ------------------------------------------------ #
    if _bullets(method, 3):
        steps = _bullets(method, limit=4, width=64)
        pages.append({
            "layout": "roadmap",
            "kicker": "02 · METHOD",
            "title": "研究方法",
            "subtitle": _clean(method.heading if method else "研究设计", 40),
            "data": {
                "aside": {
                    "title": "怎么做的",
                    "body": steps[0] if steps else "",
                    "items": [_clean(s, 26) for s in steps[1:4]],
                    "footer": f"原文页码：p{method.page}" if method else "",
                },
                "steps": [{"no": f"{i + 1:02d}", "title": _clean(s, 22), "body": _clean(s, 70),
                           "meta": f"p{method.page}" if method else ""}
                          for i, s in enumerate(steps[:4])],
            },
        })
    else:
        questions = _bullets(intro, limit=3, width=70)
        if questions:
            pages.append({
                "layout": "big_number",
                "kicker": "02 · QUESTIONS",
                "title": "研究问题",
                "data": {
                    "mode": "hero",
                    "items": [{"number": f"{i + 1:02d}", "title": _clean(q, 26), "body": _clean(q, 80),
                               "tone": ["primary", "accent", "neutral"][i % 3]}
                              for i, q in enumerate(questions)],
                },
            })

    # 04 results chart ----------------------------------------------------- #
    if chart:
        kpis = []
        for item in numbers[:3]:
            tone = "flat"
            value = _percent_value(item["value"])
            if value is not None:
                tone = "up" if value > 0 else "down"
            kpis.append({"value": item["value"], "label": _clean(item["context"], 18),
                         "note": f"p{item['page']}", "tone": tone})
        cards = []
        for bullet in _bullets(results, limit=2, width=70):
            cards.append({"title": _clean(bullet, 22), "body": _clean(bullet, 90),
                          "tone": "tint" if not cards else "plain"})
        pages.append({
            "layout": "chart_insight",
            "kicker": "03 · RESULTS",
            "title": "主要结果",
            "subtitle": "数值从 PDF 文本提取，请回原页核对",
            "hero": True,
            "data": {
                "side_ratio": 0.60,
                "chart": chart,
                "kpis": kpis,
                "cards": cards,
                "takeaway": {"label": "一句话",
                             "text": _clean((_bullets(results, 1, 90)
                                             or [_number_sentence(numbers)])[0], 90)},
            },
        })

    # 05 figure evidence ---------------------------------------------------- #
    figures = digest.best_figures(max_figures)
    for position, fig in enumerate(figures):
        cards: List[Dict[str, Any]] = []
        for bullet in _bullets(results or discussion, limit=2, width=66):
            cards.append({"title": _clean(bullet, 20), "body": _clean(bullet, 80),
                          "tone": "tint" if not cards else "plain"})
        pages.append({
            "layout": "image_evidence",
            "kicker": f"0{4 + position} · EVIDENCE",
            "title": _clean(fig.caption or "论文配图", 40),
            "data": {
                "side_ratio": 0.62,
                "image": {
                    "path": fig.path or "",
                    "caption": _clean(fig.caption or f"第 {fig.page} 页配图", 70),
                    "source": f"来源：{_source_note(digest, fig.page)}",
                    "fit": "contain",
                },
                "cards": cards or [{"title": "怎么读这张图",
                                    "body": _clean(fig.caption or "请人工补一句读图提示。", 60),
                                    "tone": "plain"}],
                "takeaway": {"label": "解读", "text": "图与表相互印证；引用图片请核对原文版权。"},
            },
        })

    # 06 table -------------------------------------------------------------- #
    table_rows: Optional[List[List[str]]] = None
    table_page = 0
    for candidate in digest.tables:
        rows = _usable_table(candidate)
        if rows:
            table_rows, table_page = rows, int(candidate["page"])
            break
    if table_rows:
        pages.append({
            "layout": "data_table",
            "kicker": "APPENDIX · A1",
            "title": "原文表格（自动提取）",
            "subtitle": "列名与数值需人工校对",
            "data": {
                "columns": table_rows[0][:4],
                "rows": table_rows[1:] or table_rows,
                "caption": f"来源：{_source_note(digest, table_page)} · 自动提取，务必回页核对",
                "highlight_col": -1,
                "first_col_bold": True,
            },
        })

    # 07 findings ----------------------------------------------------------- #
    figures_banner = []
    for item in numbers[:3]:
        value = _percent_value(item["value"])
        tone = "flat"
        if value is not None:
            tone = "up" if value > 0 else "down"
        figures_banner.append({"value": item["value"], "unit": "", "label": _clean(item["context"], 18),
                               "tone": tone})
    if not figures_banner:
        figures_banner = [{"value": str(digest.pages), "unit": "页", "label": "论文篇幅", "tone": "flat"}]
    finding_cards = []
    for bullet in _bullets(results or discussion, limit=3, width=64):
        finding_cards.append({"title": _clean(bullet, 22), "body": _clean(bullet, 90),
                              "tone": ["plain", "tint", "primary"][len(finding_cards) % 3]})
    if not finding_cards:
        # No usable prose left after the bibliography filter: quote the extracted
        # numbers instead of shipping an empty page with "请人工补一条".
        for item in numbers[:2]:
            finding_cards.append({
                "title": _clean(item["value"], 12),
                "body": _clean(item["context"], 80) + f"（p{item['page']}）",
                "tone": ["plain", "tint"][len(finding_cards) % 2]})
    if not finding_cards:
        finding_cards = [{"title": "自动提取有限", "body": "请对照原文结果章节补一条发现。", "tone": "plain"}]
    pages.append({
        "layout": "key_findings",
        "kicker": "FINDINGS",
        "title": "关键发现",
        "data": {
            "banner": {"heading": "需要记住的数字", "figures": figures_banner},
            "cards": finding_cards,
            "cards_ratio": 0.36,
        },
    })

    # 08 closing ------------------------------------------------------------ #
    # Prefer a real closing section; otherwise quote the last section we have, so
    # the page never ships with a "please fill this in" placeholder.
    quote_source = conclusion or discussion or results or (digest.sections[-1] if digest.sections else None)
    quote = (_bullets(quote_source, 1, 110) or ["（原文未提取到结论句，请人工补一句。）"])[0]
    panels = []
    for label, section, tone in (("局限", conclusion, "plain"), ("展望", discussion or conclusion, "primary")):
        bullets = _bullets(section, limit=1, width=90)
        panels.append({"title": label,
                       "body": bullets[0] if bullets else
                       f"自动提取未覆盖该部分，请对照原文第 {digest.pages} 页前后补充。",
                       "tone": tone})
    pages.append({
        "layout": "closing",
        "kicker": "CONCLUSION",
        "title": "总结",
        "data": {
            "quote": {"text": _clean(quote, 110), "source": _source_note(digest)},
            "panels": panels,
            "thanks": "感谢聆听 · 欢迎批评指正",
        },
    })

    deck = {
        "meta": {
            "title": title,
            "subtitle": _clean(digest.title if re.search(r"[A-Za-z]", digest.title) else "", 90),
            "kicker": kicker,
            "journal": journal or digest.year or "",
            "authors": digest.authors[:4],
            "source_note": _source_note(digest),
            "footer_note": " · ".join(b for b in (kicker, _clean(title, 40)) if b),
            "language": "zh",
        },
        "pages": pages,
    }
    _balance_heroes(pages)
    return json.loads(json.dumps(deck, ensure_ascii=False))     # plain JSON types only


def _balance_heroes(pages: List[Dict[str, Any]], target: float = 0.42) -> None:
    """Keep the peak-to-valley rhythm honest on short decks.

    ``cover`` / ``key_findings`` / ``closing`` are hero pages by layout, so an
    8-page skeleton would hit 50% and trip R002.  Explicit ``hero: true`` flags
    (the results page) are the only ones we may drop.
    """
    def is_hero(page: Dict[str, Any]) -> bool:
        return bool(page.get("hero")) or page.get("layout") in tokens.HERO_LAYOUTS

    explicit = [page for page in pages if page.get("hero") is True]
    while pages and explicit:
        count = sum(1 for page in pages if is_hero(page))
        if count / len(pages) <= target:
            return
        explicit.pop(0)["hero"] = False


# --------------------------------------------------------------------------- #
# model authoring (OpenAI-compatible endpoint)
# --------------------------------------------------------------------------- #


SYSTEM_PROMPT = """你是学术汇报 PPT 的内容作者。请把论文摘要包改写成 Deep Ocean 风格的 deck 文档，只输出 JSON。

硬性要求：
1. 只使用摘要包里出现的事实与数字；每个数字后面如有页码请保留页码。禁止编造数据、公式或引用。
2. 结构：首尾必须是 cover 与 closing；中间 6–10 页；每页 layout 必须是下列之一：
   {layouts}
3. 每页字段必须严格符合该 layout 的契约（字段名、类型），不要新增字段：
{schema}
4. 节奏：hero 页面（cover/key_findings/closing 以及标注 "hero": true 的页）约占 1/3，
   相邻页不要用同一个 layout；宁可少一页也不要让某一页空。
5. 文字风格：中文、克制、每页一个判断（"所以呢"），标题不超过 20 字，卡内正文不超过 60 字。
6. 配图：最多 {max_figures} 页 image_evidence，且只使用摘要包 figures 里给出的 path；
   没有合适配图就不要用这个 layout。
7. 只输出一个 JSON 对象，形如 {{"meta": {{...}}, "pages": [...]}}，不要输出解释或 Markdown 代码块。"""


def _schema_prompt() -> str:
    lines: List[str] = []
    for name in schema.LAYOUT_NAMES:
        cfg = schema.LAYOUTS[name]
        fields = ", ".join(f"{f}{'*' if s['required'] else ''}" for f, s in cfg["fields"].items())
        lines.append(f"- {name}（{cfg['zh']}）: {fields}")
    return "\n".join(lines)


def build_messages(digest: Digest, *, max_figures: int = MAX_FIGURE_PAGES) -> List[Dict[str, str]]:
    system = SYSTEM_PROMPT.format(layouts=", ".join(schema.LAYOUT_NAMES),
                                  schema=_schema_prompt(), max_figures=max_figures)
    user = (digest.to_markdown() + "\n\n"
            f"可选配图（最多 {max_figures} 张）：\n" +
            "\n".join(f"- path={f.path}  第{f.page}页  {f.caption or '(无图注)'}"
                      for f in digest.best_figures(4)))
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def chat(messages: Sequence[Dict[str, str]], *, base_url: str = DEFAULT_BASE_URL,
         model: str = DEFAULT_MODEL, api_key: Optional[str] = None,
         temperature: float = 0.2, timeout: int = 120) -> str:
    """One OpenAI-compatible chat completion, using stdlib urllib only."""
    key = api_key or next((os.environ[name] for name in API_KEY_ENV if os.environ.get(name)), "")
    if not key:
        raise RuntimeError(
            "no API key found. Export one of " + ", ".join(API_KEY_ENV) +
            ' (or pass --api-key). Without a key use the offline skeleton instead.')
    payload = json.dumps({"model": model, "messages": list(messages),
                          "temperature": temperature,
                          "response_format": {"type": "json_object"}},
                         ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        base_url.rstrip("/") + "/chat/completions", data=payload,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"},
        method="POST")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:  # pragma: no cover - network dependent
        detail = exc.read().decode("utf-8", "replace")[:400]
        raise RuntimeError(f"model call failed ({exc.code}): {detail}") from exc
    except urllib.error.URLError as exc:  # pragma: no cover - network dependent
        raise RuntimeError(f"model call failed: {exc.reason}") from exc
    return body["choices"][0]["message"]["content"]


def _strip_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    start, end = text.find("{"), text.rfind("}")
    return text[start:end + 1] if start >= 0 and end > start else text


def llm_deck(digest: Digest, *, base_url: str = DEFAULT_BASE_URL, model: str = DEFAULT_MODEL,
             api_key: Optional[str] = None, max_figures: int = MAX_FIGURE_PAGES,
             retries: int = 1) -> Tuple[Dict[str, Any], List[str]]:
    """Ask a model for a deck, validate it, and repair it once if needed.

    Returns ``(deck_dict, notes)``; raises ``RuntimeError`` when even the repair
    round cannot produce a valid document.
    """
    messages = build_messages(digest, max_figures=max_figures)
    notes: List[str] = []
    last_problems: List[str] = []
    for attempt in range(retries + 1):
        raw = chat(messages, base_url=base_url, model=model, api_key=api_key)
        try:
            data = json.loads(_strip_fences(raw))
        except json.JSONDecodeError as exc:
            last_problems = [f"模型返回的不是合法 JSON：{exc}"]
            messages = messages + [{"role": "user", "content": "上一次输出无法解析，请只输出 JSON 对象。"}]
            continue
        deck = spec.Deck.from_dict(data)
        problems = spec.validate(deck, schema.field_table())
        if not problems:
            notes.append(f"模型出稿通过校验（第 {attempt + 1} 次尝试）。")
            return data, notes
        last_problems = problems
        notes.append(f"第 {attempt + 1} 次出稿有 {len(problems)} 个问题，已要求模型修正。")
        messages = messages + [
            {"role": "assistant", "content": _strip_fences(raw)[:4000]},
            {"role": "user", "content": "这份 deck 校验失败，请修正后重新输出完整 JSON：\n- "
                                        + "\n- ".join(problems[:12])},
        ]
    raise RuntimeError("model could not produce a valid deck:\n  - " + "\n  - ".join(last_problems[:12]))
