# -*- coding: utf-8 -*-
"""Deep Ocean Slides — an academic 16:9 deck design system that is code.

``import deepocean`` stays importable without python-pptx so that the tokens,
the spec model and the HTML renderer can be used on their own::

    from deepocean import tokens
    tokens.hex_of("navy")        # '#1B3A5C'

Heavier modules (primitives, layouts, build, check, html) are imported lazily.
"""

from __future__ import annotations

from . import color, spec, tokens, units

__version__ = tokens.VERSION

__all__ = ["color", "spec", "tokens", "units", "__version__",
           "primitives", "layouts", "build", "check", "html", "charts"]

_LAZY = ("primitives", "layouts", "build", "check", "html", "charts", "cli")


def __getattr__(name: str):
    """Import PPTX-dependent submodules only when they are actually used."""
    if name in _LAZY:
        import importlib

        module = importlib.import_module(f".{name}", __name__)
        globals()[name] = module
        return module
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
