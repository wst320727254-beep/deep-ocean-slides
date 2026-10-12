# -*- coding: utf-8 -*-
"""Regenerate ``examples/*.yaml|json`` from :mod:`deepocean.examples_data`.

The example decks are derived from the bundled Python data so that ``deepocean
demo`` (which ships in the wheel) and ``examples/`` (which lives in the repo)
can never drift apart.  CI runs this and fails when the working tree changes.

    python tools/sync_examples.py            # write
    python tools/sync_examples.py --check    # verify, exit 1 on drift
"""

from __future__ import annotations

import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from deepocean import examples_data, spec  # noqa: E402

TARGETS = (
    ("demo-deck", examples_data.DEMO_DECK),
    ("minimal-deck", examples_data.MINIMAL_DECK),
)

HEADER = (
    "# Deep Ocean Slides — 示例 deck（由 tools/sync_examples.py 从 src/deepocean/examples_data.py 生成）\n"
    "# 修改示例请改 examples_data.py 后重新运行：python tools/sync_examples.py\n"
)


def render(name: str, data: dict) -> dict:
    """Return {relative path: text} for one example deck."""
    deck = spec.Deck.from_dict(json.loads(json.dumps(data)))
    yaml_text = spec.dumps_yaml(deck.to_dict())
    json_text = json.dumps(deck.to_dict(), ensure_ascii=False, indent=2) + "\n"
    return {
        f"examples/{name}.yaml": HEADER + yaml_text,
        f"examples/{name}.json": json_text,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="只校验是否与代码同步")
    args = parser.parse_args(argv)

    drift = []
    for name, data in TARGETS:
        for rel, text in render(name, data).items():
            path = os.path.join(ROOT, rel)
            current = None
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as fh:
                    current = fh.read()
            if current == text:
                print(f"= {rel}")
                continue
            if args.check:
                print(f"! {rel} 与 examples_data.py 不同步")
                drift.append(rel)
                continue
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(text)
            print(f"✓ {rel}")
    return 1 if drift else 0


if __name__ == "__main__":
    raise SystemExit(main())
