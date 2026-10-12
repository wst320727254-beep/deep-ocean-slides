# -*- coding: utf-8 -*-
"""Paper -> digest: turn a PDF into something a deck can be authored from.

The extractor is deterministic and offline (no model calls, no network): it
reads the PDF with :mod:`pypdf`, finds the sections, the table-like blocks, the
numbers that are worth putting on a slide, and the embedded figures.

Its output is a :class:`Digest` plus a Markdown rendering (``paper.digest.md``).
That file is the *prompt payload*: hand it to an LLM (``--llm``), or read it
yourself and fill in a ``deck.yaml`` — either way the numbers on the slides are
traceable to the paper, which is the whole point of the style guide.

Requires the optional extra::

    pip install "deep-ocean-slides[paper]"
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

# Sections we look for, in digest order.  Matching is case-insensitive and
# tolerant of numbering ("3.2 Method", "二、研究方法", "ABSTRACT").
SECTION_PATTERNS: List[Tuple[str, str]] = [
    ("abstract", r"(abstract|摘要)"),
    ("introduction", r"(introduction|引言|绪论|研究背景|背景)"),
    ("related", r"(related work|literature|文献综述|相关工作)"),
    ("theory", r"(theory|hypothes|理论|假设|框架)"),
    ("method", r"(method|methodology|research design|experiment|data|方法|研究设计|实验|数据)"),
    ("results", r"(result|finding|empirical|结果|发现)"),
    ("mechanism", r"(mechanism|moderat|heterogene|机制|异质性|调节)"),
    ("discussion", r"(discussion|implication|讨论|启示)"),
    ("conclusion", r"(conclusion|limitation|future|结论|局限|展望)"),
]

#: Numbers a quantitative deck usually needs.
NUMBER_PATTERNS: List[Tuple[str, str]] = [
    ("percent", r"[+-]?\d+(?:\.\d+)?\s?%"),
    ("significance", r"p\s?[<>=]\s?0?\.\d+|p\s?<\s?0\.0\d|\*{1,3}"),
    ("sample", r"\bN\s?=\s?[\d,，]{3,}"),
    ("coefficient", r"[+-]?\d+\.\d{2,4}(?!\d)"),
    ("count", r"\b\d{1,3}(?:,\d{3}){1,}\b"),
]

#: Figures smaller than this are logos, rules or bullets, not evidence.
MIN_FIGURE_PX = 180
MIN_FIGURE_BYTES = 12_000

#: Exported figures are downscaled to this width: a 8000px heatmap has no more
#: information on a 1280px slide, and it would bloat both the PNG and the .pptx.
MAX_FIGURE_W = 1600

#: Caption words that mark a figure as *slide-worthy* (framework, main result)
#: over a wall of robustness heatmaps.
FIGURE_KEYWORDS: Tuple[Tuple[str, int], ...] = (
    ("framework", 6), ("conceptual", 6), ("mechanism", 5), ("overview", 5),
    ("main result", 6), ("main effect", 6), ("research model", 6),
    ("identification", 4), ("design", 4), ("trend", 3), ("distribution", 2),
    ("框架", 6), ("机制", 5), ("概览", 5), ("主效应", 6), ("研究设计", 4),
    ("结果", 3), ("模型", 3),
)

#: Caption openers, Latin and Chinese.
CAPTION_RE = re.compile(
    r"^\s*(fig(?:ure)?\.?\s*\d+[a-z]?|table\s*\d+[a-z]?|图\s*\d+[a-z]?|表\s*\d+[a-z]?)"
    r"\s*[.:：、]?\s*(.{4,90})",
    re.IGNORECASE,
)


@dataclass
class Figure:
    """One embedded raster image that survived the size filters."""

    page: int
    index: int
    width: int
    height: int
    path: Optional[str] = None          # written PNG, when --figures was given
    bytes_: int = 0
    caption: str = ""
    kind: str = "image"                 # image | chart

    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in self.__dict__.items() if v not in ("", None, 0)}


@dataclass
class Section:
    key: str
    heading: str
    page: int
    text: str

    def bullets(self, limit: int = 5, width: int = 90) -> List[str]:
        """Sentence-ish bullets, long enough to be useful, short enough to fit."""
        parts: List[str] = []
        for chunk in re.split(r"(?<=[。！？.!?])\s*", self.text):
            chunk = " ".join(chunk.split())
            if len(chunk) < 12:
                continue
            parts.append(chunk if len(chunk) <= width else chunk[: width - 1] + "…")
            if len(parts) >= limit:
                break
        return parts


@dataclass
class Digest:
    """Everything the authoring step may use, with provenance."""

    path: str
    title: str = ""
    subtitle: str = ""
    authors: List[str] = field(default_factory=list)
    year: str = ""
    pages: int = 0
    sections: List[Section] = field(default_factory=list)
    tables: List[Dict[str, Any]] = field(default_factory=list)
    numbers: List[Dict[str, Any]] = field(default_factory=list)
    figures: List[Figure] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    # -- queries ----------------------------------------------------------- #
    def section(self, key: str) -> Optional[Section]:
        for item in self.sections:
            if item.key == key:
                return item
        return None

    def text_of(self, *keys: str) -> str:
        return "\n".join(item.text for item in self.sections if item.key in keys)

    def top_numbers(self, limit: int = 8) -> List[Dict[str, Any]]:
        """The most slide-worthy numbers: percentages first, then samples."""
        order = {"percent": 0, "significance": 1, "sample": 2, "coefficient": 3, "count": 4}
        seen: set = set()
        out: List[Dict[str, Any]] = []
        for item in sorted(self.numbers, key=lambda n: order.get(n["kind"], 9)):
            key = (item["kind"], item["value"])
            if key in seen:
                continue
            seen.add(key)
            out.append(item)
            if len(out) >= limit:
                break
        return out

    def best_figures(self, limit: int = 3) -> List[Figure]:
        """The most slide-worthy figures: captioned, on-topic, not a heatmap wall.

        "合适的图片" is ranked, not guessed: a caption that names a framework or a
        main result wins, a captionless image loses, and extreme aspect ratios
        (long strips, square matrices) are pushed down.
        """
        def score(fig: Figure) -> Tuple[int, float, int]:
            text = (fig.caption or "").lower()
            keyword = sum(weight for word, weight in FIGURE_KEYWORDS if word in text)
            ratio = fig.width / max(1, fig.height)
            shape = 1.0 if 0.9 <= ratio <= 2.4 else 0.5
            return (keyword * 10 + (20 if fig.caption else 0), shape * min(fig.width, 2400), -fig.page)

        return sorted(self.figures, key=score, reverse=True)[:limit]

    # -- rendering --------------------------------------------------------- #
    def to_markdown(self, max_chars_per_section: int = 900) -> str:
        lines: List[str] = [f"# 论文摘要包 / paper digest", ""]
        lines += [
            f"- 文件：`{os.path.basename(self.path)}`",
            f"- 标题：{self.title or '(未识别)'}",
            f"- 作者：{', '.join(self.authors) if self.authors else '(未识别)'}",
            f"- 年份：{self.year or '(未识别)'}",
            f"- 页数：{self.pages}",
            "",
        ]
        if self.sections:
            lines += ["## 章节与节选", ""]
            for item in self.sections:
                text = " ".join(item.text.split())
                if len(text) > max_chars_per_section:
                    text = text[: max_chars_per_section] + "…"
                lines += [f"### {item.heading}  (p{item.page})", "", text, ""]
        if self.tables:
            lines += ["## 候选表格", ""]
            for i, table in enumerate(self.tables, 1):
                lines += [f"### 表 {i}（p{table['page']}）", "", "```", table["text"], "```", ""]
        numbers = self.top_numbers(12)
        if numbers:
            lines += ["## 可用数字（含出处页）", "", "| 类型 | 数值 | 页 | 上下文 |", "|---|---|---:|---|"]
            for item in numbers:
                lines.append(f"| {item['kind']} | `{item['value']}` | {item['page']} | {item['context']} |")
            lines.append("")
        if self.figures:
            lines += ["## 候选配图", "", "| # | 页 | 尺寸 | 图注 | 文件 |", "|---|---:|---|---|---|"]
            for i, fig in enumerate(self.figures, 1):
                lines.append(f"| {i} | {fig.page} | {fig.width}×{fig.height} | "
                             f"{fig.caption or '(无)'} | `{fig.path or '(未导出)'}` |")
            lines.append("")
        if self.warnings:
            lines += ["## 提取提示", ""] + [f"- {w}" for w in self.warnings] + [""]
        lines += [
            "---",
            "",
            "> 下一步：`deepocean from-paper <pdf> --llm` 让模型按 `deck.yaml` 结构出稿，",
            "> 或人为照 `deepocean layouts <layout>` 填字段；所有数字请回原页核对。",
            "",
        ]
        return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Extraction
# --------------------------------------------------------------------------- #


def _reader(path: str):
    try:
        from pypdf import PdfReader
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise RuntimeError(
            'reading PDFs needs pypdf. Install it with `pip install "deep-ocean-slides[paper]"`.'
        ) from exc
    return PdfReader(path)


def _page_text(page: Any) -> str:
    for mode in ("layout", None):
        try:
            text = page.extract_text(extraction_mode=mode) if mode else page.extract_text()
        except Exception:
            continue
        if text and text.strip():
            return text
    return ""


def _match_section(line: str) -> Optional[Tuple[str, str]]:
    stripped = line.strip().strip("：:").strip()
    if not stripped or len(stripped) > 60:
        return None
    # Drop a leading number ("3.2 ", "二、" "III ")
    body = re.sub(r"^\s*(?:[0-9]+(?:\.[0-9]+)*|[一二三四五六七八九十]+|[IVX]+)[.、)）]?\s*", "", stripped)
    if not body:
        return None
    for key, pattern in SECTION_PATTERNS:
        if re.fullmatch(pattern, body, re.IGNORECASE) or re.match(rf"^{pattern}\b", body, re.IGNORECASE):
            return key, stripped
    return None


def _split_sections(pages: Sequence[str]) -> List[Section]:
    sections: List[Section] = []
    current: Optional[Section] = None
    for number, text in enumerate(pages, 1):
        for raw in text.splitlines():
            hit = _match_section(raw)
            if hit:
                if current and current.text.strip():
                    sections.append(current)
                current = Section(key=hit[0], heading=hit[1].strip(), page=number, text="")
                continue
            if current is not None:
                current.text += raw + "\n"
    if current and current.text.strip():
        sections.append(current)
    # Keep the first occurrence of each key in document order.
    seen: set = set()
    unique: List[Section] = []
    for item in sections:
        if item.key in seen:
            continue
        seen.add(item.key)
        unique.append(item)
    return unique


def _tables(pages: Sequence[str], limit: int = 6) -> List[Dict[str, Any]]:
    """Blocks of 3+ consecutive lines with 2+ space-separated columns."""
    tables: List[Dict[str, Any]] = []
    for number, text in enumerate(pages, 1):
        block: List[str] = []
        for raw in text.splitlines() + [""]:
            columns = re.split(r"\s{2,}", raw.strip())
            looks_tabular = len(columns) >= 3 and len(raw.strip()) > 12
            if looks_tabular and not re.match(r"^[-—=_\s]+$", raw.strip()):
                block.append(" | ".join(columns))
                continue
            if len(block) >= 3:
                tables.append({"page": number, "text": "\n".join(block)})
                if len(tables) >= limit:
                    return tables
            block = []
    return tables


def _numbers(pages: Sequence[str], limit: int = 60) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for number, text in enumerate(pages, 1):
        for line in text.splitlines():
            clean = " ".join(line.split())
            if len(clean) < 4:
                continue
            for kind, pattern in NUMBER_PATTERNS:
                for match in re.finditer(pattern, clean):
                    value = match.group(0).strip()
                    if kind == "coefficient" and not re.search(r"[<>=*−-]", clean):
                        continue          # bare decimals are usually page numbers
                    if kind == "significance" and len(value) < 2:
                        continue
                    out.append({
                        "kind": kind,
                        "value": value,
                        "page": number,
                        "context": clean[:70] + ("…" if len(clean) > 70 else ""),
                    })
                    if len(out) >= limit:
                        return out
    return out


def _captions(pages: Sequence[str]) -> Dict[int, List[str]]:
    captions: Dict[int, List[str]] = {}
    for number, text in enumerate(pages, 1):
        found: List[str] = []
        for line in text.splitlines():
            match = CAPTION_RE.match(line)
            if match:
                found.append(f"{match.group(1)} {match.group(2)}".strip())
        captions[number] = found
    return captions


def _figures(reader: Any, out_dir: Optional[str], pages: Sequence[str],
             limit: int = 12) -> Tuple[List[Figure], List[str]]:
    figures: List[Figure] = []
    warnings: List[str] = []
    captions = _captions(pages)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    for page_number, page in enumerate(reader.pages, 1):
        try:
            images = list(page.images)
        except Exception as exc:  # pragma: no cover - malformed PDFs
            warnings.append(f"第 {page_number} 页图片提取失败：{exc}")
            continue
        for index, image in enumerate(images, 1):
            try:
                pil = image.image if hasattr(image, "image") else None
            except Exception:
                pil = None
            if pil is None:
                try:
                    import io

                    from PIL import Image

                    pil = Image.open(io.BytesIO(image.data))
                except Exception:
                    continue
            width, height = pil.size
            size = len(getattr(image, "data", b"") or b"")
            if width < MIN_FIGURE_PX or height < MIN_FIGURE_PX or size < MIN_FIGURE_BYTES:
                continue                      # logo / rule / icon
            ratio = width / max(1, height)
            kind = "chart" if 0.6 <= ratio <= 4.0 else "image"
            page_captions = captions.get(page_number) or []
            caption = page_captions[min(index - 1, len(page_captions) - 1)] if page_captions else ""
            path = None
            if out_dir:
                stem = f"p{page_number:02d}-fig{index:02d}"
                path = os.path.join(out_dir, stem + ".png")
                try:
                    image_out = pil.convert("RGB")
                    if image_out.width > MAX_FIGURE_W:
                        ratio = MAX_FIGURE_W / image_out.width
                        image_out = image_out.resize(
                            (MAX_FIGURE_W, max(1, int(image_out.height * ratio))),
                            getattr(pil, "Resampling", None).LANCZOS if hasattr(pil, "Resampling") else 1)
                    image_out.save(path, "PNG", optimize=True)
                except Exception:
                    path = None
            figures.append(Figure(page=page_number, index=index, width=width, height=height,
                                  path=path, bytes_=size, caption=caption, kind=kind))
            if len(figures) >= limit:
                return figures, warnings
    return figures, warnings


#: Metadata title sanity: journal stamps are not a paper title.
STAMP_RE = re.compile(
    r"(submitted|manuscript|draft|revision|working paper|preprint|journal|volume|issue|doi|"
    r"copyright|all rights reserved|elsevier|springer|informs)",
    re.IGNORECASE)

#: Headings that are never the title of page 1.
HEADING_RE = re.compile(r"^(abstract|摘要|keywords|关键词|introduction|引言|绪论)\b", re.IGNORECASE)


def title_by_font(page: Any, max_len: int = 150) -> str:
    """The page-1 title is the text set in the largest type — read it, not guess.

    A PDF page carries journal stamps, running heads and the abstract in the
    same text stream; font size is the one signal that separates the title from
    all of them.
    """
    chunks: List[Tuple[float, str]] = []

    def visit(text: str, cm: Any, tm: Any, font_dict: Any, font_size: Any) -> None:
        clean = " ".join(str(text or "").split())
        try:
            size = float(font_size)
        except (TypeError, ValueError):
            return
        if clean and size > 0:
            chunks.append((round(size, 1), clean))

    try:
        page.extract_text(visitor_text=visit)
    except Exception:
        return ""
    if not chunks:
        return ""
    largest = max(size for size, _ in chunks)
    picked = [text for size, text in chunks if size >= largest - 0.6]
    title = " ".join(picked).strip()
    if len(title) < 8:
        return ""
    return title[:max_len]


def guess_title(first_page: str) -> str:
    """Fallback when font sizes are unavailable: first substantial line."""
    lines = [" ".join(line.split()) for line in (first_page or "").splitlines()]
    usable = [line for line in lines
              if 14 <= len(line) <= 140
              and not STAMP_RE.search(line)
              and not HEADING_RE.match(line)
              and "@" not in line
              and not line.endswith(",")]
    for line in usable:
        if not line.endswith("."):          # a title rarely ends in a full stop
            return line
    return usable[0] if usable else ""


def extract(path: str, figures_dir: Optional[str] = None) -> Digest:
    """Read a PDF into a :class:`Digest` (offline, deterministic)."""
    if not os.path.exists(path):
        raise FileNotFoundError(path)
    reader = _reader(path)
    meta = getattr(reader, "metadata", None) or {}
    pages = [_page_text(page) for page in reader.pages]

    title = str(meta.get("/Title") or "").strip()
    if STAMP_RE.search(title):
        title = ""          # journal stamp, not the paper's title
    if not title and pages:
        try:
            title = title_by_font(reader.pages[0])
        except Exception:
            title = ""
        if not title:
            title = guess_title(pages[0])
    authors_raw = str(meta.get("/Author") or "")
    authors = [a.strip() for a in re.split(r"[;,、]| and ", authors_raw) if a.strip()]
    year = ""
    match = re.search(r"(19|20)\d{2}", str(meta.get("/CreationDate") or "") + " " + (pages[0][:400] if pages else ""))
    if match:
        year = match.group(0)

    digest = Digest(
        path=os.path.abspath(path),
        title=title,
        authors=authors,
        year=year,
        pages=len(pages),
        sections=_split_sections(pages),
        tables=_tables(pages),
        numbers=_numbers(pages),
    )
    digest.figures, warnings = _figures(reader, figures_dir, pages)
    digest.warnings = warnings

    if not digest.sections:
        digest.warnings.append("没有识别到章节标题；digest 只有数字与配图，需要人工补结构。")
    if not digest.figures:
        digest.warnings.append("没有提取到可用配图（矢量图与内嵌小图不计入）。")
    return digest


def digest_for_deck(digest: Digest, *, max_pages: int = 14) -> Dict[str, Any]:
    """A compact, model-friendly view (also handy for tests)."""
    return {
        "title": digest.title,
        "authors": digest.authors,
        "year": digest.year,
        "pages": digest.pages,
        "max_deck_pages": max_pages,
        "sections": [{"key": s.key, "heading": s.heading, "page": s.page,
                      "excerpt": " ".join(s.text.split())[:400]} for s in digest.sections],
        "numbers": digest.top_numbers(10),
        "tables": [{"page": t["page"], "text": t["text"][:400]} for t in digest.tables[:3]],
        "figures": [{"page": f.page, "path": f.path, "caption": f.caption,
                     "size": f"{f.width}x{f.height}"} for f in digest.best_figures(3)],
    }
