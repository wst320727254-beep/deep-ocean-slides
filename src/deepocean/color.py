# -*- coding: utf-8 -*-
"""Colour maths: parsing, hue tests, contrast, and palette guardrails."""

from __future__ import annotations

import colorsys
from typing import Dict, Iterable, List, Optional, Tuple

from . import tokens

RGB = Tuple[int, int, int]


def hex_to_rgb(value: str) -> RGB:
    """``"#1B3A5C"`` / ``"1b3a5c"`` -> ``(27, 58, 92)``."""
    s = value.strip().lstrip("#")
    if len(s) == 3:
        s = "".join(c * 2 for c in s)
    if len(s) != 6:
        raise ValueError(f"not a hex colour: {value!r}")
    return (int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16))


def rgb_to_hex(rgb: RGB) -> str:
    return "#{:02X}{:02X}{:02X}".format(*rgb)


def hex_to_hls(value: str) -> Tuple[float, float, float]:
    """Return ``(hue_deg, lightness_0_1, saturation_0_1)``."""
    r, g, b = (c / 255.0 for c in hex_to_rgb(value))
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    return (h * 360.0, l, s)


def relative_luminance(value: str) -> float:
    """WCAG 2.x relative luminance."""
    def channel(c: int) -> float:
        cs = c / 255.0
        return cs / 12.92 if cs <= 0.03928 else ((cs + 0.055) / 1.055) ** 2.4

    r, g, b = hex_to_rgb(value)
    return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)


def contrast_ratio(fg: str, bg: str) -> float:
    """WCAG contrast ratio, 1.0 - 21.0."""
    l1, l2 = relative_luminance(fg), relative_luminance(bg)
    hi, lo = max(l1, l2), min(l1, l2)
    return round((hi + 0.05) / (lo + 0.05), 2)


def palette_key(value: str) -> Optional[str]:
    """Reverse-lookup a hex value to its token name, if it is on-palette."""
    v = value.upper()
    for key, sw in tokens.PALETTE.items():
        if sw.hex == v:
            return key
    for key, sw in tokens.TEXT_COLORS.items():
        if sw.hex == v:
            return key
    return None


def is_allowed(value: str, extra: Iterable[str] = ()) -> bool:
    """True when a colour belongs to the Deep Ocean palette."""
    allowed = {h.upper() for h in tokens.allowed_hexes()} | {h.upper() for h in extra}
    return value.upper() in allowed


def forbidden_reason(value: str) -> Optional[str]:
    """Explain why a colour breaks the guide, or ``None`` when it is fine."""
    v = value.upper()
    hue, _light, sat = hex_to_hls(v)
    for rule in tokens.FORBIDDEN:
        if rule["kind"] == "hex" and v == str(rule["value"]).upper():
            return f"{rule['reason_zh']} / {rule['reason_en']}"
        if rule["kind"] == "hue":
            lo, hi = float(rule["lo"]), float(rule["hi"])
            if sat >= float(rule["min_sat"]) and lo <= hue <= hi:
                return f"{rule['reason_zh']} / {rule['reason_en']}"
    return None


def audit_colour(value: str) -> Dict[str, object]:
    """One-stop report used by the linter for a single colour."""
    return {
        "hex": value.upper(),
        "on_palette": is_allowed(value),
        "token": palette_key(value),
        "forbidden": forbidden_reason(value),
        "hue": round(hex_to_hls(value)[0], 1),
        "saturation": round(hex_to_hls(value)[2], 3),
        "contrast_on_white": contrast_ratio(value, "#FFFFFF"),
    }


def mix(a: str, b: str, weight_b: float = 0.5) -> str:
    """Linear blend, handy for tint ramps and hover states."""
    ra, ga, ba = hex_to_rgb(a)
    rb, gb, bb = hex_to_rgb(b)
    w = max(0.0, min(1.0, weight_b))
    return rgb_to_hex((round(ra + (rb - ra) * w),
                       round(ga + (gb - ga) * w),
                       round(ba + (bb - ba) * w)))


def tint(value: str, amount: float = 0.9, base: str = "#FFFFFF") -> str:
    """Lighten a colour towards ``base`` (0 = unchanged, 1 = base)."""
    return mix(value, base, amount)


def scale_ramp(keys: List[str], steps: int) -> List[str]:
    """Evenly sample ``steps`` colours out of a list of palette keys."""
    if steps <= 0 or not keys:
        return []
    if steps == 1:
        return [tokens.hex_of(keys[0])]
    out: List[str] = []
    for i in range(steps):
        pos = i * (len(keys) - 1) / (steps - 1)
        lo = int(pos)
        hi = min(lo + 1, len(keys) - 1)
        out.append(mix(tokens.hex_of(keys[lo]), tokens.hex_of(keys[hi]), pos - lo))
    return out
