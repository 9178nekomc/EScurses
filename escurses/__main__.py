"""``python -m escurses`` 入口。"""

from __future__ import annotations

import sys

from .demo import main

if __name__ == "__main__":
    sys.exit(main())
