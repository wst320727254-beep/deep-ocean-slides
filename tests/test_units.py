# -*- coding: utf-8 -*-
"""Unit-conversion contract: px is the pivot, everything else is derived.

Run with ``pytest tests/test_units.py`` (or ``python tests/test_units.py``).
"""

from __future__ import annotations

import math

from deepocean import tokens, units


def test_px_to_pt_is_the_powerpoint_constant():
    assert units.PT_PER_PX == 0.75
    assert units.px_to_pt(30) == 22.5
    assert units.px_to_pt(44) == 33.0
    assert units.px_to_pt(0) == 0.0


def test_pt_to_px_round_trips():
    for px in (8, 11, 12.5, 13, 14, 30, 44, 72, 440):
        assert math.isclose(units.pt_to_px(units.px_to_pt(px)), px, rel_tol=1e-9)


def test_px_to_inch_round_trips():
    for px in (0, 40, 60, 720, 1280):
        assert math.isclose(units.inch_to_px(units.px_to_inch(px)), px, rel_tol=1e-9)


def test_canvas_is_thirteen_point_three_three_inches_wide():
    assert math.isclose(units.px_to_inch(1280), 13.3333, abs_tol=1e-4)
    assert math.isclose(units.px_to_inch(1280), 1280 / 96.0, rel_tol=1e-12)


def test_canvas_height_is_seven_point_five_inches():
    assert math.isclose(units.px_to_inch(720), 7.5, abs_tol=1e-12)
    assert tokens.CANVAS["height_in"] == 7.5


def test_emu_round_trip_against_python_pptx():
    # 1 inch == 914400 EMU, so 96px == 1in == 914400 EMU.
    assert units.px_to_emu(96) == 914400
    assert units.px_to_emu(1280) == 12192000      # PowerPoint 16:9 slide width
    assert units.px_to_emu(720) == 6858000
    for px in (0, 1, 40, 60, 200, 440, 1280):
        emu = units.px_to_emu(px)
        assert isinstance(emu, int)
        assert math.isclose(emu / units.EMU_PER_INCH * units.PX_PER_INCH, px, abs_tol=0.51)


def test_cm_and_mm_conversions():
    assert math.isclose(units.px_to_cm(40), 1.0583, abs_tol=1e-3)
    assert math.isclose(units.px_to_cm(1280), 33.8667, abs_tol=1e-3)
    assert math.isclose(units.px_to_mm(96), 25.4, abs_tol=1e-9)
    assert math.isclose(units.px_to_cm(96), 2.54, abs_tol=1e-9)


def test_screenshot_quality_targets():
    """The scaling factors the guide promises for Retina / 4K exports."""
    assert units.TARGETS["pptx-16:9"] == (1280, 720, 1.0)
    assert units.TARGETS["keynote-1080p"] == (1920, 1080, 1.5)
    assert units.TARGETS["figma-2x"] == (2560, 1440, 2.0)
    assert units.TARGETS["4k"] == (3840, 2160, 3.0)

    # 1080p / 2x / 4K canvases are exact integer multiples of the design grid,
    # which is what keeps a scaled screenshot pixel-crisp.
    for name, (width, height, factor) in units.TARGETS.items():
        assert math.isclose(units.scale_for(width), factor), name
        assert math.isclose(width / height, 16 / 9, rel_tol=1e-9), name
        assert math.isclose(units.scale_value(40, width), 40 * factor), name
    assert units.scale_for(1920, 1080) == 1.5


def test_scaling_constants_keep_the_grid_aligned():
    # A 40px margin and a 20px gutter must stay whole numbers at every target.
    for width, _height, factor in units.TARGETS.values():
        for design_px in (tokens.SAFE_MARGIN_PX, tokens.CARD_GAP_PX):
            assert float(units.scale_value(design_px, width)).is_integer()
        assert factor in (1.0, 1.5, 2.0, 3.0)


def test_conversion_table_is_well_formed_markdown():
    table = units.conversion_table()
    lines = table.splitlines()
    assert lines[0].startswith("| px | pt (PowerPoint) | inch | cm |")
    assert "---" in lines[1]
    assert len(lines) == 2 + 10
    for line in lines[2:]:
        cells = [c.strip() for c in line.strip("|").split("|")]
        assert len(cells) == 6
        assert math.isclose(float(cells[1]), units.px_to_pt(float(cells[0])), abs_tol=0.01)
        assert math.isclose(float(cells[2]), units.px_to_inch(float(cells[0])), abs_tol=1e-4)


if __name__ == "__main__":  # pragma: no cover - manual runner fallback
    passed = 0
    for name, fn in sorted(list(globals().items())):
        if name.startswith("test_") and callable(fn):
            fn()
            passed += 1
    print(f"test_units: {passed} tests passed")
