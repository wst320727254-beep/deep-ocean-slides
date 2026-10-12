# -*- coding: utf-8 -*-
"""Regenerate ``assets/preview.png`` — the contact sheet in the README.

Renders the reference deck the long way round so the picture proves the *PPTX*
(not just the HTML preview) actually looks like the design:

    deck -> .pptx            (our generator)
    .pptx -> .pdf            (LibreOffice, headless, isolated profile)
    .pdf -> .png per page    (poppler's pdftoppm)
    pages -> contact sheet   (Pillow)

Every step degrades with a clear message, so contributors without LibreOffice
or poppler can still run the rest of the tool-chain.

    python tools/make_preview.py                       # 6 pages, 2 columns
    python tools/make_preview.py --pages 1,6,7,9,11,12 --cols 2 --scale 0.5
"""

from __future__ import annotations

import argparse
import glob
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

DEFAULT_PAGES = "1,6,7,8,9,11"
SOFFICE_CANDIDATES = (
    r"C:\Program Files\LibreOffice\program\soffice.exe",
    r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
    "/Applications/LibreOffice.app/Contents/MacOS/soffice",
    "/usr/bin/soffice",
    "/usr/bin/libreoffice",
)


def find_tool(candidates, name: str) -> str:
    found = shutil.which(name)
    if found:
        return found
    for candidate in candidates:
        if os.path.exists(candidate):
            return candidate
    raise SystemExit(
        f"找不到 {name}。请安装 LibreOffice（转 PDF）与 poppler-utils（转 PNG），"
        f"或用 --skip-render 自己准备图片。"
    )


def find_pdftoppm() -> str:
    found = shutil.which("pdftoppm")
    if found:
        return found
    pattern = os.path.join(
        os.environ.get("LOCALAPPDATA", ""),
        "Microsoft", "WinGet", "Packages", "*Poppler*", "**", "bin", "pdftoppm.exe")
    hits = glob.glob(pattern, recursive=True)
    if hits:
        return hits[0]
    raise SystemExit("找不到 pdftoppm（poppler-utils）。")


def build_deck(out_pptx: str, deck_path: str = "") -> str:
    """Build the bundled reference deck, or any deck given with ``--deck``."""
    from deepocean import build, examples_data, spec

    if deck_path:
        deck = spec.Deck.load(deck_path)
    else:
        deck = spec.Deck.from_dict(examples_data.DEMO_DECK)
    result = build.build(deck, out_pptx)
    print(f"✓ PPTX  {result.path}  ({result.pages} 页)")
    return result.path


def to_pdf(pptx: str, workdir: str) -> str:
    soffice = find_tool(SOFFICE_CANDIDATES, "soffice")
    # LibreOffice wants a file:// URL with forward slashes, even on Windows.
    profile = pathlib.Path(workdir, "lo-profile").as_posix()
    cmd = [soffice, "--headless", "--norestore", f"-env:UserInstallation=file:///{profile}",
           "--convert-to", "pdf:impress_pdf_Export", "--outdir", workdir, pptx]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise SystemExit(f"LibreOffice 转换失败（exit {proc.returncode}）\n{proc.stdout}\n{proc.stderr}")
    pdf = os.path.join(workdir, os.path.splitext(os.path.basename(pptx))[0] + ".pdf")
    if not os.path.exists(pdf):
        raise SystemExit(f"LibreOffice 没有产出 PDF：{pdf}\n{proc.stdout}\n{proc.stderr}")
    print(f"✓ PDF   {pdf}")
    return pdf


def rasterise(pdf: str, workdir: str, pages: list, dpi: int = 110) -> list:
    pdftoppm = find_pdftoppm()
    prefix = os.path.join(workdir, "page")
    high, low = max(pages), min(pages)
    subprocess.run([pdftoppm, "-png", "-r", str(dpi), "-f", str(low), "-l", str(high),
                    pdf, prefix], check=True, capture_output=True)
    files = sorted(glob.glob(prefix + "*.png"))
    if not files:
        raise SystemExit("pdftoppm 没有产出图片。")
    print(f"✓ PNG   {len(files)} 页 -> {workdir}")
    return files


def contact_sheet(images: list, out_path: str, cols: int = 2, gap: int = 18,
                  page_w: int = 620, bg: str = "#EEF1F5") -> str:
    from PIL import Image

    cells = []
    for path in images:
        img = Image.open(path).convert("RGB")
        ratio = page_w / img.width
        cells.append(img.resize((page_w, int(img.height * ratio)), Image.LANCZOS))
    if not cells:
        raise SystemExit("没有可用于拼图的页面。")

    cell_h = max(c.height for c in cells)
    rows = (len(cells) + cols - 1) // cols
    pad = gap
    width = pad + cols * (page_w + pad)
    height = pad + rows * (cell_h + pad)
    sheet = Image.new("RGB", (width, height), bg)

    for index, cell in enumerate(cells):
        r, c = divmod(index, cols)
        x = pad + c * (page_w + pad)
        y = pad + r * (cell_h + pad)
        sheet.paste(cell, (x, y))

    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    sheet.save(out_path, "PNG", optimize=True)
    print(f"✓ PNG   {out_path}  ({sheet.width}x{sheet.height})")
    return out_path


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", default=os.path.join(ROOT, "assets", "preview.png"))
    parser.add_argument("--deck", default="", help="要预览的 deck.yaml（默认内置参考 deck）")
    parser.add_argument("--pages", default=DEFAULT_PAGES, help="逗号分隔的页码，1 起")
    parser.add_argument("--cols", type=int, default=2)
    parser.add_argument("--dpi", type=int, default=110)
    parser.add_argument("--width", type=int, default=620, help="每页在拼图中的宽度 px")
    parser.add_argument("--keep", default="", help="保留中间产物到该目录（默认临时目录）")
    parser.add_argument("--skip-render", action="store_true",
                        help="跳过 pptx/pdf 渲染，直接用 --keep 里的 page-*.png")
    args = parser.parse_args(argv)

    pages = [int(p) for p in args.pages.split(",") if p.strip()]
    workdir = args.keep or tempfile.mkdtemp(prefix="deepocean-preview-")
    os.makedirs(workdir, exist_ok=True)
    print(f"工作目录 {workdir}")

    if args.skip_render:
        images = sorted(glob.glob(os.path.join(workdir, "page*.png")))
    else:
        # Clear stale page images from an earlier run, otherwise the contact
        # sheet silently mixes pages of two different decks.
        for stale in glob.glob(os.path.join(workdir, "page*.png")):
            try:
                os.remove(stale)
            except OSError:
                pass
        pptx = build_deck(os.path.join(workdir, "deep-ocean-demo.pptx"), args.deck)
        pdf = to_pdf(pptx, workdir)
        all_pages = rasterise(pdf, workdir, pages, dpi=args.dpi)
        images = [all_pages[p - min(pages)] for p in pages if 1 <= p - min(pages) + 1 <= len(all_pages)]

    return 0 if contact_sheet(images, args.out, cols=args.cols, page_w=args.width) else 1


if __name__ == "__main__":
    raise SystemExit(main())
