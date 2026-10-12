# -*- coding: utf-8 -*-
"""Unit conversions for porting Deep Ocean to any slide tool.

The design is authored on a **1280 x 720 px** canvas, so ``px`` is the pivot
unit::

    pt    = px * 0.75            # PowerPoint / Keynote font size
    inch  = px / 96              # PowerPoint position
    cm    = px * 0.026458
    EMU   = px / 96 * 914400     # python-pptx internal unit

Targets that do not use 1280x720 simply scale every px value:

===============  =========  ==========================================
Target           factor     note
===============  =========  ==========================================
1280 x 720       1.0        design size
1920 x 1080      1.5        Keynote 16:9 default, Canva, Figma @1.5x
2560 x 1440      2.0        Figma @2x, Retina export
3840 x 2160      3.0        4K export
===============  =========  ==========================================
"""

from __future__ import annotations

from typing import Dict, Tuple

PX_PER_INCH = 96.0
EMU_PER_INCH = 914400
PT_PER_PX = 0.75
CM_PER_PX = 2.54 / 96.0           # 0.0264583
MM_PER_PX = 25.4 / 96.0

#: Named output targets -> (width, height, scale factor).
TARGETS: Dict[str, Tuple[int, int, float]] = {
    "pptx-16:9": (1280, 720, 1.0),
    "keynote-1080p": (1920, 1080, 1.5),
    "figma-2x": (2560, 1440, 2.0),
    "4k": (3840, 2160, 3.0),
}


def px_to_pt(px: float) -> float:
    """1280x720 px -> PowerPoint points (font size)."""
    return px * PT_PER_PX


def px_to_inch(px: float) -> float:
    return px / PX_PER_INCH


def px_to_cm(px: float) -> float:
    return px * CM_PER_PX


def px_to_mm(px: float) -> float:
    return px * MM_PER_PX


def px_to_emu(px: float) -> int:
    """pixels -> English Metric Units, the unit python-pptx stores."""
    return int(round(px / PX_PER_INCH * EMU_PER_INCH))


def pt_to_px(pt: float) -> float:
    return pt / PT_PER_PX


def inch_to_px(inch: float) -> float:
    return inch * PX_PER_INCH


def scale_for(width_px: int, height_px: int = 0) -> float:
    """Scale factor to reach another canvas width (height optional)."""
    return width_px / 1280.0


def scale_value(px: float, width_px: int = 1280) -> float:
    """Scale one designed px value to a different canvas width."""
    return px * scale_for(width_px)


def conversion_table(values=(8, 12, 14, 20, 40, 60, 72, 120, 200, 440)) -> str:
    """Markdown table of common px values in every supported unit."""
    rows = ["| px | pt (PowerPoint) | inch | cm | Keynote 1920 | Figma 2560 |",
            "|---:|---:|---:|---:|---:|---:|"]
    for v in values:
        rows.append(
            f"| {v} | {px_to_pt(v):.2f} | {px_to_inch(v):.4f} | {px_to_cm(v):.3f} "
            f"| {v * 1.5:.1f} | {v * 2:.1f} |"
        )
    return "\n".join(rows)
