# -*- coding: utf-8 -*-
"""Draw the sample figure used by ``image_evidence`` in the bundled example.

The repo must not ship a third-party paper figure, so this tool draws a
licence-free schematic with Pillow in the Deep Ocean palette:

    python tools/make_sample_figure.py      # -> examples/assets/concept-framework.png

It is intentionally plain (boxes, arrows, one label) — the point of the example
is the *layout*, not the artwork.  Replace this file with a real figure of your
own (or your paper's, if you have the rights) when you build a live deck.
"""

from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from PIL import Image, ImageDraw  # noqa: E402

from deepocean import tokens, units  # noqa: E402

W, H = 1200, 760                      # drawn at 2x the slide slot for crisp print
NAVY = tokens.hex_of("navy")
TEAL = tokens.hex_of("teal")
GRAY = tokens.hex_of("grayblue")
INK = tokens.hex_of("t1")
FAINT = tokens.hex_of("t3")
LIGHT = tokens.hex_of("light")
MINT = tokens.hex_of("mint")
WHITE = "#FFFFFF"


def _font(size: int, bold: bool = False):
    from PIL import ImageFont

    candidates = [
        r"C:\Windows\Fonts\msyhbd.ttc" if bold else r"C:\Windows\Fonts\msyh.ttc",
        r"C:\Windows\Fonts\segoeuib.ttf" if bold else r"C:\Windows\Fonts\segoeui.ttf",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc" if bold
        else "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        "/System/Library/Fonts/PingFang.ttc",
    ]
    for path in candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                continue
    return ImageFont.load_default()


def _box(draw, x, y, w, h, fill, text, sub="", color=WHITE, radius=10):
    draw.rounded_rectangle([x, y, x + w, y + h], radius=radius, fill=fill)
    lines = [(text, _font(30, True)), (sub, _font(20))]
    total = 0
    sizes = []
    for line, font in lines:
        if not line:
            continue
        bbox = draw.textbbox((0, 0), line, font=font)
        sizes.append((line, font, bbox[3] - bbox[1]))
        total += (bbox[3] - bbox[1]) + 10
    cursor = y + (h - total) / 2
    for line, font, height in sizes:
        bbox = draw.textbbox((0, 0), line, font=font)
        draw.text((x + (w - (bbox[2] - bbox[0])) / 2, cursor - bbox[1] / 2), line,
                  font=font, fill=color)
        cursor += height + 10


def _arrow(draw, x1, y1, x2, y2, color, width=6, head=20):
    draw.line([x1, y1, x2, y2], fill=color, width=width)
    draw.polygon([(x2, y2), (x2 - head, y2 - head * 0.6), (x2 - head, y2 + head * 0.6)], fill=color)


def main() -> int:
    image = Image.new("RGB", (W, H), "#FFFFFF")
    draw = ImageDraw.Draw(image)

    draw.text((60, 42), "推荐与搜索：品类决定关系", font=_font(38, True), fill=NAVY)
    draw.line([60, 108, W - 60, 108], fill=tokens.hex_of("line"), width=3)

    _box(draw, 60, 170, 300, 130, NAVY, "个性化推荐", "形成考虑集")
    _box(draw, 450, 170, 300, 130, TEAL, "主动搜索", "满足需求")
    _box(draw, 840, 170, 300, 130, GRAY, "用户决策", "下单 / 离开")

    _arrow(draw, 366, 235, 444, 235, TEAL)
    _arrow(draw, 756, 235, 834, 235, TEAL)

    draw.rounded_rectangle([60, 360, 1140, 560], radius=12, fill=MINT)
    draw.text((92, 388), "互补品类", font=_font(24, True), fill=NAVY)
    draw.text((92, 428), "推荐下降后用户去搜索深挖：搜索补回约 22%", font=_font(22), fill=INK)

    draw.rounded_rectangle([60, 590, 1140, 700], radius=12, fill=LIGHT)
    draw.text((92, 614), "替代品类", font=_font(24, True), fill=ink_brick())
    draw.text((92, 654), "推荐本身就是决策终点：搜索几乎补不回来（0%，n.s.）", font=_font(22), fill=INK)

    draw.text((60, H - 34), "示意：非论文原图，仅用于演示 image_evidence 版式", font=_font(18), fill=FAINT)

    out_dir = os.path.join(ROOT, "examples", "assets")
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, "concept-framework.png")
    image.save(path, "PNG", optimize=True)
    print(f"✓ {path}  ({image.width}x{image.height}, {os.path.getsize(path) // 1024} KB)")
    print(f"  换算：幻灯片上按 contain 缩放，1 px 图上 ≈ {round(1 / (W / 660.0), 2)} px 画布")
    print(f"  单位常数参考：1280→1920 缩放 {units.scale_for(1920):g}x")
    return 0


def ink_brick() -> str:
    return tokens.hex_of("brick")


if __name__ == "__main__":
    raise SystemExit(main())
