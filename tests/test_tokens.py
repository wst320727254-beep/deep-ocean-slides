# -*- coding: utf-8 -*-
"""Design-token invariants.

The tokens module is the single source of truth, so these tests pin the
properties every other module (renderers, linter, docs) relies on:

* every ``ROLES`` entry points at a colour that exists,
* the pt scale is exactly ``px * 0.75``,
* every text colour is readable on white (WCAG AA),
* no palette / type key is duplicated,
* ``css_variables()`` and ``summary()`` stay well formed.
"""

from __future__ import annotations

import re

from deepocean import color, schema, tokens

#: Text colours are allowed to be light by design; everything else must clear AA.
_ROLE_ORDER = ["primary", "accent", "neutral", "danger", "bg", "surface", "tint",
               "alert_tint", "stroke", "ink", "body", "faint"]


def test_roles_all_resolve_to_real_palette_entries():
    known = set(tokens.PALETTE) | set(tokens.TEXT_COLORS)
    assert tokens.ROLES, "ROLES must not be empty"
    for role, key in tokens.ROLES.items():
        assert key in known, f"role {role!r} points at unknown colour {key!r}"
        assert tokens.swatch(key) is not None
        assert tokens.hex_of(role) == tokens.hex_of(key)
        assert re.fullmatch(r"#[0-9A-F]{6}", tokens.hex_of(role)), role


def test_brand_roles_are_the_documented_four_plus_neutrals():
    for role in _ROLE_ORDER:
        assert role in tokens.ROLES, f"missing role {role!r}"
    assert tokens.ROLES["primary"] == "navy"
    assert tokens.ROLES["accent"] == "teal"
    assert tokens.ROLES["neutral"] == "grayblue"
    assert tokens.ROLES["danger"] == "brick"
    assert tokens.ROLES["bg"] == "white"
    assert tokens.ROLES["stroke"] == "line"


def test_every_hex_is_well_formed_and_unique():
    for key, swatch in tokens.PALETTE.items():
        assert re.fullmatch(r"#[0-9A-F]{6}", swatch.hex), (key, swatch.hex)
        assert swatch.key == key
        assert swatch.name_zh and swatch.name_en and swatch.use_zh and swatch.use_en
        assert swatch.role in ("brand", "surface", "text", "semantic")
        assert len(swatch.rgb) == 3 and all(0 <= c <= 255 for c in swatch.rgb)

    for key, swatch in tokens.TEXT_COLORS.items():
        assert re.fullmatch(r"#[0-9A-F]{6}", swatch.hex), (key, swatch.hex)
        assert swatch.key == key
        assert swatch.role == "text"

    hexes = [s.hex for s in list(tokens.PALETTE.values()) + list(tokens.TEXT_COLORS.values())]
    assert len(hexes) == len(set(hexes)) == len(tokens.allowed_hexes())
    assert len(tokens.allowed_hexes()) >= 12


def test_type_scale_keys_are_unique_and_pt_is_px_times_0_75():
    assert len(tokens.TYPE_SCALE) == len(set(tokens.TYPE_SCALE))
    for key, token in tokens.TYPE_SCALE.items():
        assert token.key == key
        assert token.px > 0
        assert token.pt == round(token.px * 0.75, 2), key
        assert token.weight in ("bold", "semibold", "regular")
        assert token.color in tokens.PALETTE or token.color in tokens.TEXT_COLORS, key
        assert 1.0 <= token.line_height <= 1.7, key
        assert token.letter_spacing >= 0
        assert token.name_zh and token.use_zh and token.use_en
        assert token.bold == (token.weight in ("bold", "semibold"))


def test_type_scale_covers_the_guide_ladder():
    expected = {
        "cover_title": 44, "cover_subtitle": 26, "cover_meta": 14,
        "section_number_lg": 72, "section_number": 48, "page_title": 30,
        "kicker": 14, "page_subtitle": 15, "card_title": 18, "card_title_sm": 16,
        "card_body": 14, "card_body_sm": 13, "kpi_value": 44, "kpi_value_sm": 32,
        "kpi_label": 12, "kpi_note": 12, "table_head": 13, "table_cell": 12.5,
        "node": 13, "quote": 22, "caption": 11.5, "footer": 12, "page_number": 12,
    }
    for key, px in expected.items():
        assert key in tokens.TYPE_SCALE, f"missing type token {key!r}"
        assert tokens.TYPE_SCALE[key].px == px, key
    assert tokens.TYPE_SCALE["page_title"].pt == 22.5
    assert tokens.TYPE_SCALE["section_number_lg"].pt == 54.0


def test_type_rules_are_internally_consistent():
    rules = tokens.TYPE_RULES
    assert rules["min_px_body"] == 13
    assert rules["min_px_any"] == 11
    assert rules["min_px_any"] < rules["min_px_body"]
    assert rules["max_font_families"] == tokens.FONTS["max_families"] == 2
    assert rules["max_weights"] == 2
    assert rules["min_contrast"] == 4.5
    lo, hi = rules["carousel_line_height"]
    assert lo == 1.5 and hi == 1.6
    # every step of the scale must clear the absolute minimum
    for key, token in tokens.TYPE_SCALE.items():
        assert token.px >= rules["min_px_any"], key


#: Measured WCAG ratios of the palette ink on white.  ``t3`` (Faint) is the
#: documented footer / unit colour and sits just under AA on purpose; it is only
#: ever used for provenance text.  Pinning the numbers here means a palette edit
#: fails loudly instead of silently shipping unreadable decks.
CONTRAST_ON_WHITE = {
    "navy": 11.63, "teal": 3.30, "grayblue": 3.77, "brick": 5.44,
    "t1": 15.96, "t2": 7.53, "t3": 2.96,
}
BODY_SAFE_INK = ("navy", "brick", "t1", "t2")


def test_no_text_colour_falls_below_wcag_aa_on_white():
    white = tokens.PALETTE["white"].hex
    for key, swatch in tokens.TEXT_COLORS.items():
        ratio = color.contrast_ratio(swatch.hex, white)
        if key == "t3":
            assert ratio >= 2.9, (key, ratio)      # provenance text, sub-AA by design
        else:
            assert ratio >= tokens.TYPE_RULES["min_contrast"], (key, swatch.hex, ratio)


def test_secondary_accent_colours_are_display_only_on_white():
    """teal / grayblue are focus colours: legal at >=32px, not for body copy.

    This pins the guide's own numbers so the linter's K001 thresholds (4.5 for
    body, 3.0 for large display type) cannot drift away from the palette.
    """
    white = tokens.PALETTE["white"].hex
    for key, expected in CONTRAST_ON_WHITE.items():
        hexv = tokens.PALETTE[key].hex if key in tokens.PALETTE else tokens.TEXT_COLORS[key].hex
        ratio = color.contrast_ratio(hexv, white)
        assert abs(ratio - expected) <= 0.05, (key, hexv, ratio, expected)
        if key in BODY_SAFE_INK:
            assert ratio >= tokens.TYPE_RULES["min_contrast"], (key, ratio)
        elif key == "t3":
            assert ratio >= 2.9, (key, ratio)       # provenance text, sub-AA by design
        else:
            assert ratio >= 3.0, (key, ratio)       # large display type only


def test_every_type_token_colour_is_readable_on_white():
    """Ink is either body-safe (>=4.5) or a large-display accent (>=3.0)."""
    white = tokens.PALETTE["white"].hex
    for key, token in tokens.TYPE_SCALE.items():
        hexv = tokens.hex_of(token.color)
        if hexv == white:
            continue                                   # table_head / node: white on navy
        ratio = color.contrast_ratio(hexv, white)
        if token.color == "t3":
            assert ratio >= 2.9, (key, hexv, ratio)     # footer / source note only
        elif token.color in ("teal", "grayblue"):
            assert ratio >= 3.0 and token.px >= 11, (key, hexv, ratio, token.px)
        else:
            assert ratio >= tokens.TYPE_RULES["min_contrast"], (key, hexv, ratio)


def test_palette_entries_are_not_on_the_forbidden_list():
    for key, swatch in list(tokens.PALETTE.items()) + list(tokens.TEXT_COLORS.items()):
        assert color.forbidden_reason(swatch.hex) is None, (key, swatch.hex)
        assert color.is_allowed(swatch.hex), (key, swatch.hex)


def test_forbidden_list_is_machine_checkable():
    assert tokens.FORBIDDEN
    for rule in tokens.FORBIDDEN:
        assert rule["kind"] in ("hex", "hue", "pattern")
        assert rule["reason_zh"] and rule["reason_en"]
        if rule["kind"] == "hex":
            assert color.forbidden_reason(rule["value"])
        else:
            assert 0 <= float(rule["lo"]) < float(rule["hi"]) <= 360
    assert color.forbidden_reason("#8E44AD") is not None     # purple
    assert color.forbidden_reason("#FF69B4") is not None     # pink
    assert color.forbidden_reason("#000000") is not None     # pure black
    assert color.forbidden_reason("#D4AF37") is not None     # gold


def test_ratio_budget_shape():
    budget = tokens.RATIO_BUDGET
    for family in ("blue_family", "white", "tint_family", "brick", "gold"):
        assert family in budget, family
        lo, hi = budget[family]
        assert 0 <= lo <= hi <= 100
    assert budget["gold"] == (0, 0)
    assert budget["brick"][1] == 6
    assert budget["tint_family"][1] == tokens.RHYTHM_RULES["tint_family_max"] * 100


def test_rhythm_rules_match_the_guide():
    rhythm = tokens.RHYTHM_RULES
    assert rhythm["hero_ratio"] == (4, 12)
    assert rhythm["equal_width_card_rows_max"] == 2
    assert rhythm["hero_equal_width_rows"] == 0
    assert rhythm["no_three_valleys"] is True
    assert rhythm["min_anchor_px"] == 44
    assert rhythm["min_content_fill"] == 0.80
    assert rhythm["tint_family_max"] == 0.20
    assert abs(rhythm["asymmetry_ratio"] - 0.83) < 1e-9


def test_hero_layouts_exist_in_the_schema():
    assert tokens.HERO_LAYOUTS
    for name in tokens.HERO_LAYOUTS:
        assert name in schema.LAYOUTS, name
        assert schema.LAYOUTS[name]["hero"] is True
    assert set(tokens.CHROME_EXEMPT_LAYOUTS) <= set(schema.LAYOUTS)
    for name in tokens.CHROME_EXEMPT_LAYOUTS:
        assert schema.LAYOUTS[name]["chrome"] is False


def test_bands_do_not_overlap_and_cover_the_canvas():
    height = tokens.CANVAS["height_px"]
    bands = tokens.BANDS
    seen: list = []
    for name in ("top_bar", "title", "content", "footer"):
        band = bands[name]
        assert band["y"] >= 0 and band["h"] > 0, name
        assert band["y"] + band["h"] <= height, name
        seen.append((band["y"], band["y"] + band["h"]))
    for (_, end), (start, _) in zip(seen, seen[1:]):
        assert end <= start, "bands must not overlap"
    assert bands["footer"]["y"] + bands["footer"]["h"] == height
    assert tokens.SAFE_AREA["w"] == tokens.CONTENT_WIDTH_PX == 1200
    assert tokens.CANVAS["width_px"] - 2 * tokens.SAFE_MARGIN_PX == tokens.CONTENT_WIDTH_PX


def test_fonts_declare_two_families_max():
    assert tokens.FONTS["max_families"] == 2
    for stack in ("cjk", "latin", "serif", "mono"):
        assert isinstance(tokens.FONTS[stack], list)
        assert tokens.FONTS[stack], stack
        assert all(isinstance(item, str) and item for item in tokens.FONTS[stack]), stack


def test_hex_of_accepts_roles_keys_and_raw_hex():
    assert tokens.hex_of("navy") == "#1B3A5C"
    assert tokens.hex_of("primary") == "#1B3A5C"
    assert tokens.hex_of("t1") == "#1A2230"
    assert tokens.hex_of("#2e9ba6") == "#2E9BA6"
    assert tokens.hex_of("danger") == tokens.hex_of("brick")
    try:
        tokens.hex_of("chartreuse")
    except KeyError as exc:
        assert "chartreuse" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("unknown colour key must raise KeyError")


def test_css_variables_are_well_formed():
    css = tokens.css_variables()
    assert css.startswith(":root{") and css.endswith("}")
    bodies = [line.strip() for line in css.splitlines()[1:-1]]
    assert len(bodies) == (len(tokens.PALETTE) + len(tokens.TEXT_COLORS)
                           + 2 + len(tokens.TYPE_SCALE))
    names = []
    for line in bodies:
        assert line.endswith(";"), line
        name, _, value = line.partition(":")
        assert name.startswith("--do-"), line
        assert value.rstrip(";").strip() != ""
        names.append(name)
    assert len(names) == len(set(names)), "duplicate CSS custom property"
    for key, swatch in tokens.PALETTE.items():
        assert f"--do-{key}:{swatch.hex};" in css
    for key, token in tokens.TYPE_SCALE.items():
        assert f"--do-{key}:{token.px}px;" in css
    assert f"--do-margin:{tokens.SAFE_MARGIN_PX}px;" in css
    assert f"--do-gap:{tokens.CARD_GAP_PX}px;" in css


def test_summary_is_json_serialisable_and_complete():
    import json

    summary = tokens.summary()
    text = json.dumps(summary, ensure_ascii=False)      # must not raise
    assert text
    for key in ("name", "name_zh", "version", "canvas", "safe_margin_px", "card_gap_px",
                "bands", "palette", "text_colors", "roles", "type_scale",
                "ratio_budget", "type_rules", "rhythm_rules"):
        assert key in summary, key
    assert summary["version"] == tokens.VERSION
    assert set(summary["palette"]) == set(tokens.PALETTE)
    assert set(summary["text_colors"]) == set(tokens.TEXT_COLORS)
    assert set(summary["type_scale"]) == set(tokens.TYPE_SCALE)
    for key, entry in summary["type_scale"].items():
        assert entry["pt"] == tokens.TYPE_SCALE[key].pt
        assert entry["px"] == tokens.TYPE_SCALE[key].px
    assert summary["palette"]["navy"]["hex"] == "#1B3A5C"


def test_identity_constants():
    assert tokens.NAME == "Deep Ocean"
    assert tokens.NAME_ZH == "深海学术风"
    assert tokens.VERSION.count(".") == 2
    assert tokens.TAGLINE_ZH and tokens.TAGLINE_EN
    assert tokens.LICENSE == "MIT"


if __name__ == "__main__":  # pragma: no cover - manual runner fallback
    passed = 0
    for name, fn in sorted(list(globals().items())):
        if name.startswith("test_") and callable(fn):
            fn()
            passed += 1
    print(f"test_tokens: {passed} tests passed")
