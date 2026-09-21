#!/usr/bin/env python3
"""Hook Codex SessionStart: ripresa read-only del workspace esplicitamente indicato."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def main() -> int:
    raw = os.environ.get("GF_AOS_WORKSPACE", "").strip()
    if not raw:
        return 0
    script = Path(__file__).with_name("case_lifecycle.py")
    result = subprocess.run(
        [sys.executable, str(script), "resume", raw],
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )
    if result.returncode:
        print(f"GF-AOS: ripresa non eseguita ({result.stderr.strip()})")
        return 0
    print(result.stdout.rstrip())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
