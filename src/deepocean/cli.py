# -*- coding: utf-8 -*-
"""``deepocean`` — command line interface.

::

    deepocean demo                     # build the bundled 13-page reference deck
    deepocean build deck.yaml -o out.pptx
    deepocean html  deck.yaml -o out.html
    deepocean check deck.yaml          # 自动排版自检
    deepocean preview deck.yaml        # pptx + html + 自检报告 一次产出
    deepocean init mytalk              # 写出起始 deck 模板
    deepocean layouts two_column       # 版式字段说明
    deepocean tokens --md              # 设计令牌
    deepocean units                    # 单位换算表
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any, Dict, List, Optional

from . import schema, spec as spec_mod, tokens, units

PROG = "deepocean"
EXIT_OK = 0
EXIT_FAIL = 1
EXIT_USAGE = 2


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #


def _out_path(path: str, default_name: str, out: Optional[str]) -> str:
    if out:
        if out.endswith(("/", "\\")) or os.path.isdir(out):
            return os.path.join(out, default_name)
        return out
    return os.path.join(os.path.dirname(os.path.abspath(path)) or ".", default_name)


def _load(path: str) -> spec_mod.Deck:
    if not os.path.exists(path):
        raise SystemExit(f"{PROG}: 找不到文件 {path}")
    try:
        return spec_mod.Deck.load(path)
    except spec_mod.SpecError as exc:
        raise SystemExit(f"{PROG}: 无法读取 {path}\n  {exc}")


def _stamp(text: str) -> str:
    return text


# --------------------------------------------------------------------------- #
# commands
# --------------------------------------------------------------------------- #


def cmd_from_paper(args: argparse.Namespace) -> int:
    """PDF -> digest -> deck.yaml (offline skeleton, or model-authored)."""
    from . import author, paper

    if not os.path.exists(args.pdf):
        raise SystemExit(f"{PROG}: 找不到 {args.pdf}")
    stem = os.path.splitext(os.path.basename(args.pdf))[0]
    work_dir = os.path.dirname(os.path.abspath(args.pdf))
    figures_dir = args.figures or os.path.join(work_dir, stem + ".figures")

    print(f"→ 读取 {args.pdf}")
    digest = paper.extract(args.pdf, figures_dir=figures_dir)
    print(f"  标题：{digest.title or '(未识别)'}")
    print(f"  页数 {digest.pages} · 章节 {len(digest.sections)} · 数字 {len(digest.numbers)} · "
          f"表格 {len(digest.tables)} · 配图 {len(digest.figures)}")
    for warning in digest.warnings:
        print(f"  ! {warning}")

    digest_path = args.digest or os.path.join(work_dir, stem + ".digest.md")
    with open(digest_path, "w", encoding="utf-8") as fh:
        fh.write(digest.to_markdown())
    print(f"✓ DIGEST {digest_path}")

    if args.llm:
        try:
            data, notes = author.llm_deck(digest, base_url=args.base_url, model=args.model,
                                          api_key=args.api_key, max_figures=args.max_figures)
        except RuntimeError as exc:
            print(f"! 模型出稿失败：{exc}")
            print("  退回离线骨架（不调用模型，只使用原文提取到的内容）")
            data, notes = author.skeleton_deck(digest, journal=args.journal, kicker=args.kicker,
                                               max_figures=args.max_figures, author=args.author), \
                ["离线骨架（模型不可用）"]
        else:
            for note in notes:
                print(f"  · {note}")
    else:
        data = author.skeleton_deck(digest, journal=args.journal, kicker=args.kicker,
                                    max_figures=args.max_figures, author=args.author)
        notes = ["离线骨架：只使用 PDF 中提取到的文字与数字，不会编造内容。"]
        print("  · 离线骨架（未调用模型；加 --llm 让模型改写叙事）")

    deck = spec_mod.Deck.from_dict(data)
    out = args.out or os.path.join(work_dir, stem + ".deck.yaml")
    spec_mod.Deck.save(deck, out)
    print(f"✓ DECK   {out}  ({len(deck.pages)} 页：{', '.join(deck.layouts())})")

    report = _report_for(deck, args, banner="初稿自检")
    if args.build:
        from . import build as build_mod

        pptx = os.path.splitext(out)[0] + ".pptx"
        result = build_mod.build(deck, pptx)
        print(f"✓ PPTX   {result.path}")
    return report


def cmd_normalize(args: argparse.Namespace) -> int:
    """离线修复 deck 的结构毛病（不联网、不调用模型、不改文字）。"""
    from . import repair

    if not os.path.exists(args.deck):
        raise SystemExit(f"{PROG}: 找不到 {args.deck}")
    result = repair.normalize_file(args.deck, args.out)
    target = args.out or args.deck
    if not result.changes:
        print(f"✓ {target} 结构无需修复")
        return EXIT_OK
    print(f"✓ {target} 修复 {len(result.changes)} 处结构问题")
    for change in result.changes:
        print(f"  · {change}")
    print("  下一步：deepocean check " + os.path.basename(target) + " --strict")
    return _report_for(spec_mod.Deck.load(target), args, banner="修复后自检")


def cmd_demo(args: argparse.Namespace) -> int:
    from . import build as build_mod
    from . import examples_data

    out_dir = args.out or "out"
    os.makedirs(out_dir, exist_ok=True)
    deck = spec_mod.Deck.from_dict(json.loads(json.dumps(examples_data.DEMO_DECK)))
    spec_path = deck.save(_deck_path(out_dir, "deep-ocean-demo"))
    print(f"✓ DECK  {spec_path}")
    result = build_mod.build(deck, os.path.join(out_dir, "deep-ocean-demo.pptx"))
    print(f"✓ PPTX  {result.path}  ({result.pages} 页)")
    if not args.no_html:
        try:
            from . import html as html_mod

            html_path = html_mod.write(deck, os.path.join(out_dir, "deep-ocean-demo.html"))
            print(f"✓ HTML  {html_path}")
        except ImportError as exc:  # pragma: no cover
            print(f"! HTML 渲染器不可用：{exc}")
    if args.check:
        return _report_for(deck, args, banner="内置示例 deck", already_built=result.path)
    return EXIT_OK


def _deck_path(out_dir: str, stem: str) -> str:
    """Use .yaml when PyYAML is installed (nicer to edit), else .json."""
    try:
        import yaml  # noqa: F401

        return os.path.join(out_dir, stem + ".yaml")
    except ImportError:
        return os.path.join(out_dir, stem + ".json")


def cmd_build(args: argparse.Namespace) -> int:
    from . import build as build_mod

    deck = _load(args.deck)
    out = _out_path(args.deck, _stem(args.deck) + ".pptx", args.out)
    result = build_mod.build(deck, out, check=not args.no_check, strict=args.strict)
    print(f"✓ {result.path}  ({result.pages} 页)")
    for problem in result.problems:
        print(f"! {problem}")
    if args.check:
        return _report_for(deck, args, banner="自检", already_built=result.path)
    return EXIT_OK


def cmd_html(args: argparse.Namespace) -> int:
    from . import html as html_mod

    deck = _load(args.deck)
    out = _out_path(args.deck, _stem(args.deck) + ".html", args.out)
    path = html_mod.write(deck, out, standalone=not args.fragment)
    print(f"✓ {path}")
    return EXIT_OK


def cmd_check(args: argparse.Namespace) -> int:
    from . import check as check_mod

    target = args.target
    if not os.path.exists(target):
        raise SystemExit(f"{PROG}: 找不到 {target}")
    deck = None
    if target.lower().endswith(".pptx"):
        deck = _deck_context(target, getattr(args, "deck", None))
        if deck is None:
            print("提示：未找到同名 deck 文件，版式上下文缺失（封面/结尾豁免与节奏检查会被跳过）。"
                  "用 --deck 指定，或用 `deepocean preview` 一起产出。")
    report = check_mod.check(target, deck=deck)
    if args.json:
        print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
    else:
        print(report.to_text(color=not args.no_color))
    if not report.ok():
        return EXIT_FAIL
    if args.strict and report.warnings():
        return EXIT_FAIL
    return EXIT_OK


def _deck_context(pptx_path: str, explicit: Optional[str] = None) -> Optional[spec_mod.Deck]:
    """Find the deck document that produced a .pptx.

    Looks at ``--deck``, then a sibling ``<stem>.yaml|yml|json``, then the
    one-文件 layout used by ``deepocean demo``/``preview``.
    """
    stem = os.path.splitext(pptx_path)[0]
    candidates = []
    if explicit:
        candidates.append(explicit)
    for suffix in (".yaml", ".yml", ".json"):
        candidates.append(stem + suffix)
    for candidate in candidates:
        if candidate and os.path.exists(candidate):
            try:
                return spec_mod.Deck.load(candidate)
            except spec_mod.SpecError:
                continue
    return None


def cmd_preview(args: argparse.Namespace) -> int:
    from . import build as build_mod

    deck = _load(args.deck)
    out_dir = args.out or os.path.join(os.path.dirname(os.path.abspath(args.deck)), "out")
    os.makedirs(out_dir, exist_ok=True)
    stem = _stem(args.deck)

    result = build_mod.build(deck, os.path.join(out_dir, stem + ".pptx"))
    print(f"✓ PPTX  {result.path}  ({result.pages} 页)")
    try:
        deck.save(_deck_path(out_dir, stem))
        print(f"✓ DECK  {_deck_path(out_dir, stem)}  （check 会自动读取它作为版式上下文）")
    except OSError as exc:  # pragma: no cover
        print(f"! DECK  写入失败：{exc}")
    try:
        from . import html as html_mod

        html_path = html_mod.write(deck, os.path.join(out_dir, stem + ".html"))
        print(f"✓ HTML  {html_path}")
    except ImportError as exc:  # pragma: no cover
        print(f"! HTML 渲染器不可用：{exc}")
    return _report_for(deck, args, banner="自检", already_built=result.path)


def cmd_init(args: argparse.Namespace) -> int:
    from . import examples_data

    target_dir = args.dir or "."
    os.makedirs(target_dir, exist_ok=True)
    data = examples_data.DEMO_DECK if args.demo else examples_data.MINIMAL_DECK
    deck = spec_mod.Deck.from_dict(json.loads(json.dumps(data)))
    name = "demo-deck" if args.demo else "deck"
    try:
        import yaml  # noqa: F401

        path = os.path.join(target_dir, name + ".yaml")
    except ImportError:
        path = os.path.join(target_dir, name + ".json")
    written = deck.save(path)
    print(f"✓ {written}")
    print("  下一步：")
    print(f"    {PROG} build {os.path.relpath(written)} -o out.pptx")
    print(f"    {PROG} check {os.path.relpath(written)}")
    return EXIT_OK


def cmd_layouts(args: argparse.Namespace) -> int:
    print(schema.describe(args.layout))
    if not args.layout:
        print("字段说明由 `deepocean check` 强制执行；新增版式见 docs/STYLE.md。")
    return EXIT_OK


def cmd_tokens(args: argparse.Namespace) -> int:
    if args.json:
        print(json.dumps(tokens.summary(), ensure_ascii=False, indent=2))
    elif args.css:
        print(tokens.css_variables())
    elif args.md:
        print(_tokens_markdown())
    else:
        print(_tokens_text())
    return EXIT_OK


def cmd_units(args: argparse.Namespace) -> int:
    print("# 单位换算（基准画布 1280x720 px，pt = px × 0.75）")
    print()
    print(units.conversion_table())
    return EXIT_OK


def cmd_version(args: argparse.Namespace) -> int:
    print(f"{tokens.NAME} {tokens.NAME_ZH} v{tokens.VERSION} · {tokens.LICENSE}")
    print(f"{tokens.HOMEPAGE}")
    return EXIT_OK


# --------------------------------------------------------------------------- #
# rendering helpers
# --------------------------------------------------------------------------- #


def _stem(path: str) -> str:
    return os.path.splitext(os.path.basename(path))[0]


def _report_for(deck: spec_mod.Deck, args: argparse.Namespace, banner: str = "自检",
                already_built: Optional[str] = None) -> int:
    try:
        from . import check as check_mod
    except ImportError:  # pragma: no cover
        return EXIT_OK
    report = check_mod.check_deck(deck)
    if already_built:
        try:
            pptx_report = check_mod.check_pptx(already_built, deck)
            report.issues.extend(pptx_report.issues)
            report.stats.update({f"pptx_{k}": v for k, v in pptx_report.stats.items()})
        except Exception as exc:  # pragma: no cover - never block the build
            print(f"! 版面检查跳过：{exc}")
    use_json = getattr(args, "json", False)
    if use_json:
        print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
    else:
        print(report.to_text(color=not getattr(args, "no_color", False)))
    if not report.ok():
        return EXIT_FAIL
    if getattr(args, "strict", False) and report.warnings():
        return EXIT_FAIL
    return EXIT_OK


def _tokens_text() -> str:
    lines = [f"{tokens.NAME} · {tokens.NAME_ZH} v{tokens.VERSION}",
             f"画布 {tokens.CANVAS['width_px']}x{tokens.CANVAS['height_px']} px "
             f"({tokens.CANVAS['width_in']}x{tokens.CANVAS['height_in']} in) · "
             f"安全边距 {tokens.SAFE_MARGIN_PX}px · 卡间距 {tokens.CARD_GAP_PX}px", ""]
    lines.append("色板")
    for key, sw in tokens.PALETTE.items():
        lines.append(f"  {key:<9} {sw.hex}  {sw.name_zh}  {sw.budget}".rstrip())
    for key, sw in tokens.TEXT_COLORS.items():
        lines.append(f"  {key:<9} {sw.hex}  {sw.name_zh}")
    lines.append("")
    lines.append("字号阶梯（px / pt）")
    for key, t in tokens.TYPE_SCALE.items():
        lines.append(f"  {key:<18} {t.px:>5} px / {t.pt:>6} pt  {t.weight:<8} {t.color}")
    lines.append("")
    lines.append("母版分区")
    for band, spec_ in tokens.BANDS.items():
        lines.append(f"  {band:<9} y {spec_['y']:>3} - {spec_['y'] + spec_['h']:>3}  (h {spec_['h']})")
    return "\n".join(lines)


def _tokens_markdown() -> str:
    lines = [f"# {tokens.NAME} {tokens.NAME_ZH} · 设计令牌 v{tokens.VERSION}", "",
             f"- 画布：`{tokens.CANVAS['width_px']} x {tokens.CANVAS['height_px']}` px "
             f"= `{tokens.CANVAS['width_in']} x {tokens.CANVAS['height_in']}` inch（16:9）",
             f"- 安全边距：`{tokens.SAFE_MARGIN_PX}` px · 卡片间距：`{tokens.CARD_GAP_PX}` px",
             f"- 换算：`pt = px × 0.75`，`inch = px / 96`", "",
             "## 色板", "", "| token | hex | 中文名 | English | 用途 |", "|---|---|---|---|---|"]
    for key, sw in tokens.PALETTE.items():
        lines.append(f"| `{key}` | `{sw.hex}` | {sw.name_zh} | {sw.name_en} | {sw.use_zh} |")
    lines += ["", "### 文本色", "", "| token | hex | 用途 |", "|---|---|---|"]
    for key, sw in tokens.TEXT_COLORS.items():
        lines.append(f"| `{key}` | `{sw.hex}` | {sw.use_zh} |")
    lines += ["", "## 字号阶梯", "", "| token | px | pt | 字重 | 行高 | 颜色 | 用途 |",
              "|---|---:|---:|---|---:|---|---|"]
    for key, t in tokens.TYPE_SCALE.items():
        lines.append(f"| `{key}` | {t.px:g} | {t.pt:g} | {t.weight} | {t.line_height:g} "
                     f"| `{t.color}` | {t.use_zh} |")
    lines += ["", "## 母版分区", "", "| 区 | y 起 | y 止 | 高度 |", "|---|---:|---:|---:|"]
    for band, spec_ in tokens.BANDS.items():
        lines.append(f"| {band} | {spec_['y']} | {spec_['y'] + spec_['h']} | {spec_['h']} |")
    lines += ["", "## 配比预算", "", "| 色族 | 下限 | 上限 |", "|---|---:|---:|"]
    for family, budget in tokens.RATIO_BUDGET.items():
        lo, hi = budget
        lines.append(f"| {family} | {lo}% | {hi}% |")
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# parser
# --------------------------------------------------------------------------- #


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=PROG,
        description=f"{tokens.NAME} {tokens.NAME_ZH} · 学术风 16:9 幻灯片设计系统与生成工具链"
                    f"（{tokens.TAGLINE_ZH}）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="更多用法见 https://github.com/wst320727254-beep/deep-ocean-slides",
    )
    parser.add_argument("--version", action="version",
                        version=f"{PROG} {tokens.VERSION} ({tokens.NAME})")
    sub = parser.add_subparsers(dest="command")

    p = sub.add_parser("build", help="把 deck 编译为 .pptx")
    p.add_argument("deck", help="deck.yaml / deck.json")
    p.add_argument("-o", "--out", help="输出 .pptx（默认与 deck 同目录）")
    p.add_argument("--no-check", action="store_true", help="跳过自检")
    p.add_argument("--strict", action="store_true", help="结构性错误直接中止")
    p.add_argument("--check", action="store_true", default=True,
                   help="构建后打印自检报告（默认开启）")
    p.set_defaults(func=cmd_build)

    p = sub.add_parser("html", help="渲染单文件 HTML 版（可直接打印成 PDF）")
    p.add_argument("deck")
    p.add_argument("-o", "--out")
    p.add_argument("--fragment", action="store_true", help="只要 body 片段")
    p.set_defaults(func=cmd_html)

    p = sub.add_parser("check", help="自动排版自检（规范第 09 节）")
    p.add_argument("target", help="deck.yaml / deck.json / out.pptx")
    p.add_argument("--deck", help="检查 .pptx 时显式指定对应的 deck 文件（提供版式上下文）")
    p.add_argument("--json", action="store_true", help="输出 JSON")
    p.add_argument("--strict", action="store_true", help="有警告也返回非零")
    p.add_argument("--no-color", action="store_true")
    p.set_defaults(func=cmd_check)

    p = sub.add_parser("preview", help="一次产出 pptx + html + 自检报告")
    p.add_argument("deck")
    p.add_argument("--out", help="输出目录（默认 deck 同目录下的 out/）")
    p.add_argument("--json", action="store_true")
    p.add_argument("--strict", action="store_true")
    p.add_argument("--no-color", action="store_true")
    p.set_defaults(func=cmd_preview)

    p = sub.add_parser("from-paper", help="PDF → 摘要包 → deck.yaml 初稿（可选模型改写）")
    p.add_argument("pdf", help="论文 PDF")
    p.add_argument("-o", "--out", help="输出 deck.yaml（默认与 PDF 同名的 .deck.yaml）")
    p.add_argument("--digest", help="摘要包 Markdown 输出路径")
    p.add_argument("--figures", help="配图导出目录（默认 <PDF 同名>.figures/）")
    p.add_argument("--max-figures", type=int, default=1, help="最多几页图片证据（默认 1，上限 2）")
    p.add_argument("--journal", default="", help="封面刊名角标，如 ISR · 2025")
    p.add_argument("--kicker", default="组会文献汇报", help="页眉眉标")
    p.add_argument("--author", default="", help="汇报人")
    p.add_argument("--build", action="store_true", help="顺带生成 pptx")
    p.add_argument("--llm", action="store_true", help="调用模型改写叙事（需要 API key）")
    p.add_argument("--base-url", default="https://api.deepseek.com/v1")
    p.add_argument("--model", default="deepseek-chat")
    p.add_argument("--api-key", default=None, help="也可用环境变量 DEEPSEEK_API_KEY / OPENAI_API_KEY")
    p.add_argument("--json", action="store_true")
    p.add_argument("--strict", action="store_true")
    p.add_argument("--no-color", action="store_true")
    p.set_defaults(func=cmd_from_paper)

    p = sub.add_parser("normalize", help="离线修复 deck 的结构问题（不需要 API key）")
    p.add_argument("deck")
    p.add_argument("-o", "--out", help="输出文件（默认就地写回）")
    p.add_argument("--json", action="store_true")
    p.add_argument("--strict", action="store_true")
    p.add_argument("--no-color", action="store_true")
    p.set_defaults(func=cmd_normalize)

    p = sub.add_parser("demo", help="生成内置示例 deck")
    p.add_argument("-o", "--out")
    p.add_argument("--no-html", action="store_true")
    p.add_argument("--check", action="store_true")
    p.add_argument("--json", action="store_true")
    p.add_argument("--strict", action="store_true")
    p.add_argument("--no-color", action="store_true")
    p.set_defaults(func=cmd_demo)

    p = sub.add_parser("init", help="写出起始 deck 模板")
    p.add_argument("dir", nargs="?", help="输出目录（默认当前目录）")
    p.add_argument("--demo", action="store_true", help="写出完整 13 页示例而不是 3 页模板")
    p.set_defaults(func=cmd_init)

    p = sub.add_parser("layouts", help="打印版式字段说明")
    p.add_argument("layout", nargs="?", help="版式名，省略则打印全部")
    p.set_defaults(func=cmd_layouts)

    p = sub.add_parser("tokens", help="打印设计令牌")
    g = p.add_mutually_exclusive_group()
    g.add_argument("--json", action="store_true", help="JSON（机器可读）")
    g.add_argument("--md", action="store_true", help="Markdown 表格")
    g.add_argument("--css", action="store_true", help="CSS 自定义属性")
    p.set_defaults(func=cmd_tokens)

    p = sub.add_parser("units", help="打印 px → pt/inch/cm/Keynote/Figma 换算表")
    p.set_defaults(func=cmd_units)

    p = sub.add_parser("version", help="版本信息")
    p.set_defaults(func=cmd_version)

    return parser


def _force_utf8_output() -> None:
    """Make Chinese output safe on Windows consoles.

    A stock Windows CI runner (or a ``cmd.exe`` window with cp1252/cp936) raises
    ``UnicodeEncodeError`` the moment a Chinese path or status line is printed.
    Reconfiguring the streams keeps the CLI usable everywhere; ``errors`` keeps
    it from crashing even when the terminal cannot render a glyph at all.
    """
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):  # pragma: no cover - redirected / exotic streams
            pass


def main(argv: Optional[List[str]] = None) -> int:
    _force_utf8_output()
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "command", None):
        parser.print_help()
        return EXIT_USAGE
    try:
        return int(args.func(args))
    except KeyboardInterrupt:  # pragma: no cover
        print(f"{PROG}: 已取消", file=sys.stderr)
        return 130
    except spec_mod.SpecError as exc:
        print(f"{PROG}: {exc}", file=sys.stderr)
        return EXIT_FAIL


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
