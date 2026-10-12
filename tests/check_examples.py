# -*- coding: utf-8 -*-
"""Guard rails for the shipped examples.

Run directly (``python tests/check_examples.py``) or under pytest: the file
works both ways because every check is a plain assertion inside a ``main()``.

It verifies the promise the README makes: *the examples exercise the whole
layout library, they are valid, and they contain no placeholder text.*
"""

from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from deepocean import examples_data, schema, spec  # noqa: E402

PLACEHOLDERS = ("lorem", "ipsum", "todo", "tbd", "xxx", "占位", "待填", "placeholder", "fixme")


def _texts(node) -> list:
    out = []
    if isinstance(node, dict):
        for value in node.values():
            out.extend(_texts(value))
    elif isinstance(node, (list, tuple)):
        for value in node:
            out.extend(_texts(value))
    elif isinstance(node, str):
        out.append(node)
    return out


def check_examples() -> int:
    failures = []
    covered = set()

    for label, data in (("demo-deck", examples_data.DEMO_DECK),
                        ("minimal-deck", examples_data.MINIMAL_DECK)):
        deck = spec.Deck.from_dict(data)
        covered.update(deck.layouts())

        problems = spec.validate(deck, schema.field_table())
        if problems:
            failures.append(f"{label}: {problems}")

        for i, page in enumerate(deck.pages, 1):
            for text in _texts(page.data) + [page.title]:
                low = text.lower()
                for marker in PLACEHOLDERS:
                    if marker in low:
                        failures.append(f"{label} page {i}: placeholder text {marker!r} in {text[:40]!r}")

        if len(deck.pages) < 3:
            failures.append(f"{label}: too few pages ({len(deck.pages)})")

    missing = set(schema.LAYOUT_NAMES) - covered
    if missing:
        failures.append(f"layouts never exercised by the examples: {sorted(missing)}")

    repo_demo = os.path.join(ROOT, "examples", "demo-deck.yaml")
    if os.path.exists(repo_demo):
        import json

        on_disk = spec.Deck.load(repo_demo)
        expected = spec.Deck.from_dict(json.loads(json.dumps(examples_data.DEMO_DECK)))
        if on_disk.to_dict()["pages"] != expected.to_dict()["pages"]:
            failures.append("examples/demo-deck.yaml drifted from examples_data.py "
                            "(run: python tools/sync_examples.py)")

    if failures:
        print("examples check FAILED")
        for line in failures:
            print(f"  - {line}")
        return 1
    print(f"examples check OK · layouts covered: {len(covered)}/{len(schema.LAYOUT_NAMES)}")
    return 0


def test_examples() -> None:
    assert check_examples() == 0


if __name__ == "__main__":
    raise SystemExit(check_examples())
