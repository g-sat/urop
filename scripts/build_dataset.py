"""Legacy short-statement dataset builder.

Prefer the paper dataset:
  python scripts/build_paper_dataset.py
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def main() -> None:
    script = Path(__file__).resolve().parent / "build_paper_dataset.py"
    print("forwarding to build_paper_dataset.py (paper-oriented long answers)")
    raise SystemExit(subprocess.call([sys.executable, str(script)]))


if __name__ == "__main__":
    main()
