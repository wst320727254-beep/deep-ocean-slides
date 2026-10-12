# -*- coding: utf-8 -*-
"""``python -m deepocean`` — same entry point as the ``deepocean`` script.

Both spellings are supported on purpose::

    deepocean demo -o out
    python -m deepocean demo -o out
    python -m deepocean.cli demo -o out
"""

from __future__ import annotations

import sys

from .cli import main

if __name__ == "__main__":
    sys.exit(main())
