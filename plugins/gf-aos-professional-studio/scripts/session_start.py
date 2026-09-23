#!/usr/bin/env python3
"""Hook Codex SessionStart: bootstrap minimizzato e read-only."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def main() -> int:
    raw = os.environ.get("GF_AOS_WORKSPACE", "").strip()
    if not raw:
        return 0
    script = Path(__file__).with_name("privacy_guard.py")
    result = subprocess.run(
        [sys.executable, str(script), "bootstrap", raw],
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )
    if result.returncode:
        print("GF-AOS: safe bootstrap non disponibile.")
        return 0
    print(result.stdout.rstrip())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
