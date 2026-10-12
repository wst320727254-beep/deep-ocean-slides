# -*- coding: utf-8 -*-
"""Real PowerPoint charts for the Deep Ocean deck system.

Charts are drawn with python-pptx's native chart engine (never as a picture) so
that a reviewer can click a column and read the underlying number.  This module
owns three things:

* the mapping from the frozen ``chart_insight.chart`` spec dict to a pptx plot,
* the Deep Ocean styling of that plot (palette series colours, readable data
  labels, quiet axes, no chart title — the surrounding card supplies the title),
* a height helper, because the guide requires every chart to carry an explicit
  height and a zero-height chart is a rendering bug.

Only palette colours from :mod:`deepocean.tokens` are used; series colours come
from :data:`deepocean.tokens.CHART`, and anything the caller supplies is passed
through :func:`deepocean.primitives.rgb`, which rejects off-palette values.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

from pptx.chart.data import CategoryChartData
from pptx.dml.color import RGBColor
from pptx.enum.chart import (XL_CHART_TYPE, XL_LABEL_POSITION,
                             XL_LEGEND_POSITION, XL_TICK_LABEL_POSITION)
from pptx.oxml.ns import qn
from pptx.util import Emu, Pt

from . import tokens
from .primitives import rgb
from .units import px_to_emu

__all__ = ["SUPPORTED_TYPES", "add_chart", "chart_height", "series_colors"]

#: Chart types this renderer can draw, keyed by the spec's ``type`` value.
SUPPORTED_TYPES: Dict[str, Any] = {
    "bar": XL_CHART_TYPE.COLUMN_CLUSTERED,
    "line": XL_CHART_TYPE.LINE_MARKERS,
    "doughnut": XL_CHART_TYPE.DOUGHNUT,
}

#: Default series colours, in guide order (navy, teal, grayblue, brick).
DEFAULT_SERIES: List[str] = list(tokens.CHART["series_colors"])

#: Guide window for chart heights.
MIN_HEIGHT_PX: float = float(tokens.CHART["height_px"][0])
MAX_HEIGHT_PX: float = float(tokens.CHART["height_px"][1])

#: Smallest chart text: 12px, so no label ever drops under the 11px floor.
LABEL_PX: float = 12.0


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _num(value: Any, fallback: float = 0.0) -> float:
    """Coerce a spec value to a float, tolerating ``None`` and bad strings."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(fallback)


def series_colors(count: int, theme_colors: Optional[Sequence[str]] = None) -> List[RGBColor]:
    """Resolve ``count`` series colours from the theme or the guide default.

    Args:
        count: How many distinct colours are needed.
        theme_colors: Optional palette keys / roles to prefer over the default.

    Returns:
        A list of ``count`` :class:`pptx.dml.color.RGBColor` values.
    """
    keys: List[str] = [str(k) for k in (theme_colors or []) if k] or list(DEFAULT_SERIES)
    out: List[RGBColor] = []
    for i in range(max(0, int(count))):
        out.append(rgb(keys[i % len(keys)]))
    return out


def _apply_font(font: Any, size_px: float, color: Optional[str] = None,
                bold: bool = False) -> None:
    """Style a pptx ``Font`` with a px size, a palette colour and a CJK face."""
    try:
        from .primitives import default_fonts

        latin, cjk = default_fonts()
    except (ImportError, AttributeError, TypeError):  # pragma: no cover - defensive
        latin, cjk = tokens.FONTS["latin"][0], tokens.FONTS["cjk"][0]
    try:
        font.size = Pt(round(float(size_px) * 0.75, 1))
        font.bold = bool(bold)
        if color:
            font.color.rgb = rgb(str(color))
        font.name = latin
        rPr = font._rPr
        if rPr is None:  # pragma: no cover - only for detached runs
            return
        ea = rPr.find(qn("a:ea"))
        if ea is None:
            ea = rPr.makeelement(qn("a:ea"), {})
            rPr.append(ea)
        ea.set("typeface", cjk)
    except (AttributeError, ValueError):  # pragma: no cover - defensive
        pass


def _style_axis(axis: Any, *, tick_label_pos: Optional[Any] = None,
                color: Optional[str] = None, size_px: Optional[float] = None) -> None:
    """Quiet down one chart axis: grayblue labels, no gridline clutter."""
    try:
        axis.has_major_gridlines = False
        axis.has_minor_gridlines = False
    except (AttributeError, ValueError):  # pragma: no cover
        pass
    if tick_label_pos is not None:
        try:
            axis.tick_label_position = tick_label_pos
        except (AttributeError, ValueError):  # pragma: no cover
            pass
    try:
        axis.major_tick_mark = 1  # XL_TICK_MARK.NONE
    except (AttributeError, ValueError, TypeError):  # pragma: no cover
        pass
    fmt = getattr(axis, "format", None)
    if fmt is not None:
        try:
            fmt.line.fill.background()
        except (AttributeError, ValueError):  # pragma: no cover
            pass
        try:
            _apply_font(fmt.font, size_px or LABEL_PX, color or tokens.CHART["axis_color"])
        except (AttributeError, ValueError):  # pragma: no cover
            pass


def _style_labels(plot: Any, number_format: str, size_px: float,
                  color: str = "t1") -> None:
    """Turn data labels on and make them readable (academic decks need them)."""
    if not tokens.CHART["show_data_labels"]:
        return
    try:
        plot.has_data_labels = True
        labels = plot.data_labels
        pos = getattr(XL_LABEL_POSITION, "OUTSIDE_END", None)
        if plot.chart_type == XL_CHART_TYPE.DOUGHNUT:
            pos = getattr(XL_LABEL_POSITION, "INSIDE_END", None)
        if pos is not None:
            try:
                labels.position = pos
            except ValueError:  # pragma: no cover - some plot types refuse it
                pass
        labels.number_format = number_format
        labels.number_format_is_linked = False
        _apply_font(labels.font, size_px, color, bold=True)
    except (AttributeError, ValueError):  # pragma: no cover
        pass


def _style_series(series: Any, color: RGBColor, kind: str) -> None:
    """Colour one series; doughnut/line need slightly different treatment."""
    try:
        series.format.fill.solid()
        series.format.fill.fore_color.rgb = color
    except (AttributeError, ValueError):  # pragma: no cover
        pass
    try:
        series.format.line.color.rgb = color
        series.format.line.width = Pt(1.75)
    except (AttributeError, ValueError):  # pragma: no cover
        pass
    if kind == "line":
        try:
            series.smooth = False
            series.marker.style = 8  # XL_MARKER_STYLE.CIRCLE
        except (AttributeError, ValueError, TypeError):  # pragma: no cover
            pass


def _clear_title(chart: Any) -> None:
    """Drop the auto chart title (the surrounding card supplies it)."""
    try:
        chart.has_title = False
    except (AttributeError, ValueError):  # pragma: no cover
        pass


def _borderless(chart: Any) -> None:
    """Remove the default chart border so the card frame stays in charge."""
    try:
        chart.chart_style = 2
    except (AttributeError, ValueError):  # pragma: no cover
        pass
    fmt = getattr(chart, "format", None)
    if fmt is not None:
        try:
            fmt.line.fill.background()
        except (AttributeError, ValueError):  # pragma: no cover
            pass


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #


def chart_height(chart_spec: Optional[Dict[str, Any]] = None, max_px: float = 400.0) -> float:
    """Resolve an explicit, non-zero chart height in px.

    Priority: the spec's own ``height`` (clamped into the guide window), then
    the available space when it already fits, otherwise the guide maximum.

    Args:
        chart_spec: The ``chart_insight.chart`` dict (``height`` optional).
        max_px: Space the caller can offer, in px.

    Returns:
        A float height in px, always ``>= MIN_HEIGHT_PX``.
    """
    limit = _num(max_px, MAX_HEIGHT_PX)
    explicit = _num((chart_spec or {}).get("height"), 0.0)
    if explicit > 0:
        return float(max(60.0, min(explicit, max(limit, 60.0))))
    return float(max(MIN_HEIGHT_PX, min(MAX_HEIGHT_PX, limit)))


def add_chart(slide: Any, x: float, y: float, w: float, h: float,
              chart_spec: Dict[str, Any], *,
              theme_colors: Optional[Sequence[str]] = None) -> Any:
    """Draw a native PowerPoint chart from a Deep Ocean chart spec.

    The spec shape (frozen in :mod:`deepocean.schema`) is::

        {type: "bar" | "line" | "doughnut",
         categories: ["2021", "2022"],
         series: [{name: "推荐组", values: [12, 34], color: "teal"}],
         title: "…", unit: "%", height: 320, note: "…"}

    Args:
        slide: Slide to draw on.
        x, y, w, h: Chart frame in design px.  ``h`` is always used as given;
            callers pass :func:`chart_height` so it is never zero.
        chart_spec: The chart spec dict described above.
        theme_colors: Optional palette keys overriding the default series ramp.

    Returns:
        The ``pptx.shapes.chart.Chart`` object that was added.

    Raises:
        ValueError: When the spec names an unsupported type, has no categories,
            or carries no series values.
    """
    spec = chart_spec if isinstance(chart_spec, dict) else {}
    kind = str(spec.get("type") or tokens.CHART["default_type"]).strip().lower()
    if kind not in SUPPORTED_TYPES:
        raise ValueError(
            f"unsupported chart type {kind!r}; supported types are: "
            f"{', '.join(sorted(SUPPORTED_TYPES))}"
        )

    categories = [c for c in (spec.get("categories") or []) if c is not None]
    categories = [str(c) for c in categories]
    if not categories:
        raise ValueError("chart spec needs a non-empty 'categories' list")

    series_specs: List[Dict[str, Any]] = [s for s in (spec.get("series") or []) if isinstance(s, dict)]
    if not series_specs:
        raise ValueError("chart spec needs at least one entry in 'series'")

    width = float(w)
    height = _num(h, 0.0)
    if height <= 0:
        raise ValueError("charts need an explicit height; use charts.chart_height(spec, max_px)")
    if kind in ("bar", "line") and len(series_specs) > 1:
        categories = categories[:4] or categories

    data = CategoryChartData()
    data.categories = categories
    for item in series_specs:
        values = [v for v in (item.get("values") or [])][:len(categories)]
        if not values:
            raise ValueError(f"chart series {item.get('name')!r} has no values")
        while len(values) < len(categories):
            values.append(None)
        data.add_series(str(item.get("name") or f"Series {len(data._series) + 1}"), values)

    plot = slide.shapes.add_chart(SUPPORTED_TYPES[kind], Emu(px_to_emu(x)), Emu(px_to_emu(y)),
                                  Emu(px_to_emu(width)), Emu(px_to_emu(height)),
                                  data)
    chart = plot.chart
    _clear_title(chart)
    _borderless(chart)

    explicit = [s.get("color") for s in series_specs]
    explicit = [c for c in explicit if c]
    ramp_keys = [str(c) for c in explicit] if explicit else list(theme_colors or DEFAULT_SERIES)
    ramp = series_colors(max(len(series_specs), len(categories)), ramp_keys)

    # Series colours ------------------------------------------------------ #
    for i, series in enumerate(chart.series):
        color = ramp[i % len(ramp)]
        _style_series(series, color, kind)
        if kind == "doughnut":
            # A single-series doughnut reads better with one colour per slice.
            for j, point in enumerate(series.points):
                try:
                    point.format.fill.solid()
                    point.format.fill.fore_color.rgb = ramp[j % len(ramp)]
                except (AttributeError, ValueError):  # pragma: no cover
                    pass
                try:
                    _apply_font(point.data_label.font, LABEL_PX, tokens.CHART["data_label_color"],
                                bold=True)
                except (AttributeError, ValueError):  # pragma: no cover
                    pass

    # Axes, labels, legend ------------------------------------------------ #
    if kind != "doughnut":
        try:
            value_axis = chart.value_axis
            _style_axis(value_axis, color=tokens.CHART["axis_color"], size_px=LABEL_PX)
            value_axis.has_major_gridlines = False
            value_axis.has_minor_gridlines = False
        except (AttributeError, ValueError):  # pragma: no cover
            pass
        try:
            cat_axis = chart.category_axis
            _style_axis(cat_axis, tick_label_pos=XL_TICK_LABEL_POSITION.LOW,
                        color=tokens.CHART["axis_color"], size_px=LABEL_PX)
        except (AttributeError, ValueError):  # pragma: no cover
            pass
    # A doughnut has no axes, but it still needs its slice values on the plot.
    fmt = '0"%"' if str(spec.get("unit") or "").strip() == "%" else "0.##"
    _style_labels(chart.plots[0], fmt, LABEL_PX, tokens.CHART["data_label_color"])

    try:
        chart.has_legend = True
        chart.legend.position = XL_LEGEND_POSITION.BOTTOM
        chart.legend.include_in_layout = False
        _apply_font(chart.legend.font, LABEL_PX, tokens.CHART["legend_color"])
    except (AttributeError, ValueError):  # pragma: no cover
        pass

    return chart
