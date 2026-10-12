# -*- coding: utf-8 -*-
"""Deck specification: the small, human-writable source format.

A deck is a YAML or JSON document::

    meta:
      title: 推荐如何影响消费者搜索
      subtitle: How Recommendation Affects Customer Search
      kicker: 组会文献汇报
      journal: ISR · 2025
      authors: [Yuan, Chen, Wang, Sun]
      source_note: 组会文献汇报 · ISR 2025, 36(1): 84-106
    pages:
      - layout: cover
        title: 推荐如何影响消费者搜索
        subtitle: How Recommendation Affects Customer Search
        data:
          authors: 汇报人 · 李明
          affiliation: 管理科学与工程 · 2026
      - layout: two_column
        kicker: 01 · BACKGROUND
        title: 研究背景
        data:
          left: {title: ..., body: ...}
          right: [...]

Each ``layout`` declares the fields it consumes; run ``deepocean layouts`` to
print the schema, and ``deepocean check`` to validate a document before
rendering it.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterable, List, Optional

from . import tokens

YAML_SUFFIXES = (".yaml", ".yml")
JSON_SUFFIXES = (".json",)


class SpecError(ValueError):
    """Raised when a deck document cannot be read or is structurally invalid."""


# --------------------------------------------------------------------------- #
# Document model
# --------------------------------------------------------------------------- #


@dataclass
class Page:
    """One 1280x720 canvas."""

    layout: str = "two_column"
    title: str = ""
    title_en: str = ""
    kicker: str = ""
    subtitle: str = ""
    hero: Optional[bool] = None          # None -> decided by the layout table
    data: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> "Page":
        if not isinstance(raw, dict):
            raise SpecError(f"each page must be a mapping, got {type(raw).__name__}")
        known = {"layout", "title", "title_en", "kicker", "subtitle", "hero", "data", "id", "notes"}
        page = cls(
            layout=str(raw.get("layout", "two_column")).strip(),
            title=_s(raw.get("title")),
            title_en=_s(raw.get("title_en")),
            kicker=_s(raw.get("kicker")),
            subtitle=_s(raw.get("subtitle")),
            hero=raw.get("hero"),
        )
        data = dict(raw.get("data") or {})
        # Convenience: any unknown top-level key is treated as layout data.
        for key, value in raw.items():
            if key not in known and key not in ("id", "notes"):
                data.setdefault(key, value)
        page.data = data
        if raw.get("id"):
            page.data.setdefault("id", raw["id"])
        if raw.get("notes"):
            page.data.setdefault("notes", raw["notes"])
        return page

    def to_dict(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {"layout": self.layout}
        if self.kicker:
            out["kicker"] = self.kicker
        if self.title:
            out["title"] = self.title
        if self.title_en:
            out["title_en"] = self.title_en
        if self.subtitle:
            out["subtitle"] = self.subtitle
        if self.hero is not None:
            out["hero"] = self.hero
        if self.data:
            out["data"] = self.data
        return out

    def get(self, key: str, default: Any = None) -> Any:
        """Read a layout field with a sane fallback."""
        if key in self.data:
            return self.data[key]
        return getattr(self, key, default)

    def need(self, key: str) -> Any:
        value = self.data.get(key)
        if value in (None, "", [], {}):
            raise SpecError(f"page layout={self.layout!r} is missing required field {key!r}")
        return value


@dataclass
class DeckMeta:
    title: str = "Untitled deck"
    subtitle: str = ""
    kicker: str = "组会文献汇报"
    journal: str = ""
    authors: List[str] = field(default_factory=list)
    affiliation: str = ""
    date: str = ""
    source_note: str = ""
    footer_note: str = ""
    language: str = "zh"
    #: Optional typeface override, e.g. ``{latin: Inter, cjk: Source Han Sans SC}``.
    fonts: Dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, raw: Optional[Dict[str, Any]]) -> "DeckMeta":
        raw = raw or {}
        authors = raw.get("authors") or []
        if isinstance(authors, str):
            authors = [authors]
        fonts = raw.get("fonts") or {}
        return cls(
            title=_s(raw.get("title")) or "Untitled deck",
            subtitle=_s(raw.get("subtitle")),
            kicker=_s(raw.get("kicker")) or "组会文献汇报",
            journal=_s(raw.get("journal")),
            authors=[_s(a) for a in authors],
            affiliation=_s(raw.get("affiliation")),
            date=_s(raw.get("date")),
            source_note=_s(raw.get("source_note")),
            footer_note=_s(raw.get("footer_note")),
            language=_s(raw.get("language")) or "zh",
            fonts={str(k): _s(v) for k, v in dict(fonts).items()} if isinstance(fonts, dict) else {},
        )

    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in self.__dict__.items() if v not in ("", [], None, {})}


@dataclass
class Deck:
    meta: DeckMeta = field(default_factory=DeckMeta)
    pages: List[Page] = field(default_factory=list)
    source_path: Optional[str] = None

    # -- construction ------------------------------------------------------ #
    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> "Deck":
        if not isinstance(raw, dict):
            raise SpecError("a deck document must be a mapping with 'meta' and 'pages'")
        pages_raw = raw.get("pages")
        if not pages_raw:
            raise SpecError("a deck needs at least one page under 'pages'")
        if not isinstance(pages_raw, list):
            raise SpecError("'pages' must be a list")
        return cls(meta=DeckMeta.from_dict(raw.get("meta")), pages=[Page.from_dict(p) for p in pages_raw])

    def to_dict(self) -> Dict[str, Any]:
        return {"meta": self.meta.to_dict(), "pages": [p.to_dict() for p in self.pages]}

    # -- io ---------------------------------------------------------------- #
    @classmethod
    def load(cls, path: str) -> "Deck":
        path = os.fspath(path)
        with open(path, "r", encoding="utf-8") as fh:
            text = fh.read()
        deck = loads(text, fmt=_fmt_of(path))
        deck.source_path = os.path.abspath(path)
        return deck

    def save(self, path: str) -> str:
        """Write the deck back out (YAML when PyYAML is importable, else JSON)."""
        fmt = _fmt_of(path)
        with open(path, "w", encoding="utf-8") as fh:
            if fmt == "yaml":
                fh.write(dumps_yaml(self.to_dict()))
            else:
                json.dump(self.to_dict(), fh, ensure_ascii=False, indent=2)
                fh.write("\n")
        return os.path.abspath(path)

    # -- helpers ----------------------------------------------------------- #
    def __len__(self) -> int:
        return len(self.pages)

    def __iter__(self):
        return iter(self.pages)

    def hero_count(self) -> int:
        return sum(1 for p in self.pages if is_hero(p))

    def layouts(self) -> List[str]:
        return [p.layout for p in self.pages]

    def resolved_footer_note(self) -> str:
        if self.meta.footer_note:
            return self.meta.footer_note
        bits = [b for b in (self.meta.kicker, self.meta.title, self.meta.journal) if b]
        return " · ".join(bits)


def _s(value: Any) -> str:
    return "" if value is None else str(value)


def is_hero(page: Page) -> bool:
    """Hero (peak) page?  A page-level ``hero:`` wins over the layout default."""
    if page.hero is not None:
        return bool(page.hero)
    try:
        from . import schema

        return schema.is_hero(page.layout)
    except (KeyError, ImportError):  # unknown layout: fall back to the token list
        return page.layout in tokens.HERO_LAYOUTS


# --------------------------------------------------------------------------- #
# Serialisation helpers (YAML is optional: only needed to *read* .yaml decks)
# --------------------------------------------------------------------------- #


def _fmt_of(path: str) -> str:
    lower = path.lower()
    if lower.endswith(YAML_SUFFIXES):
        return "yaml"
    return "json"


def loads(text: str, fmt: Optional[str] = None) -> Deck:
    if fmt is None:
        fmt = "json" if text.lstrip().startswith("{") else "yaml"
    if fmt == "json":
        return Deck.from_dict(json.loads(text))
    return Deck.from_dict(load_yaml(text))


def load_yaml(text: str) -> Dict[str, Any]:
    """Parse YAML, with a clear message when PyYAML is missing."""
    try:
        import yaml  # type: ignore
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise SpecError(
            "reading .yaml decks needs PyYAML. Install it with "
            '`pip install "deep-ocean-slides[yaml]"`, or write the deck as JSON.'
        ) from exc
    data = yaml.safe_load(text)
    if data is None:
        raise SpecError("the YAML document is empty")
    return data


def dumps_yaml(data: Dict[str, Any]) -> str:
    """Serialise to YAML when possible, otherwise fall back to JSON text."""
    try:
        import yaml  # type: ignore
    except ImportError:  # pragma: no cover - environment dependent
        return json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    return yaml.safe_dump(data, allow_unicode=True, sort_keys=False, width=100)


# --------------------------------------------------------------------------- #
# Validation
# --------------------------------------------------------------------------- #


def validate(deck: Deck, fields: Optional[Dict[str, Dict[str, Any]]] = None) -> List[str]:
    """Structural validation.  Returns a list of problems (empty == good).

    ``fields`` is the layout schema table published by
    :mod:`deepocean.layouts`; when omitted only generic checks run.
    """
    problems: List[str] = []
    if not deck.pages:
        problems.append("deck has no pages")
    if not deck.meta.title:
        problems.append("meta.title is empty")

    known_layouts = set(fields) if fields else None
    for i, page in enumerate(deck.pages, 1):
        where = f"page {i:02d} ({page.layout})"
        if known_layouts is not None and page.layout not in known_layouts:
            problems.append(f"{where}: unknown layout {page.layout!r}; "
                            f"known: {', '.join(sorted(known_layouts))}")
            continue
        if page.layout not in tokens.CHROME_EXEMPT_LAYOUTS and not page.title:
            problems.append(f"{where}: content pages need a title")
        if fields and page.layout in fields:
            for fname, spec in fields[page.layout].items():
                if spec.get("required") and page.data.get(fname) in (None, "", [], {}):
                    problems.append(f"{where}: missing required field {fname!r}")
    return problems


def describe_fields(fields: Dict[str, Dict[str, Any]]) -> str:
    """Render the layout schema as a Markdown table."""
    lines = ["| layout | field | type | required | note |", "|---|---|---|---|---|"]
    for name in sorted(fields):
        for fname, spec in fields[name].items():
            lines.append("| {} | {} | {} | {} | {} |".format(
                f"`{name}`", f"`{fname}`", spec.get("type", "any"),
                "yes" if spec.get("required") else "no", spec.get("note", "")))
    return "\n".join(lines)
