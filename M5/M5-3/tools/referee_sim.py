#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""裁判模拟器：S=START P=PAUSE R=RESUME E=STOP。"""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "host_side"))
from referee_bridge import RefereeBridge  # noqa: E402


def main() -> None:
    bridge = RefereeBridge(on_status=lambda s: print("status:", s))
    print("裁判模拟器: S=START P=PAUSE R=RESUME E=STOP Q=QUIT")
    try:
        import msvcrt

        while True:
            if msvcrt.kbhit():
                key = msvcrt.getwch().upper()
                if key == "Q":
                    break
                if key in "SPRE":
                    bridge.parse({"cmd": {"S": "START", "P": "PAUSE", "R": "RESUME", "E": "STOP"}[key]})
            time.sleep(0.05)
    except ImportError:
        while True:
            key = sys.stdin.read(1).upper()
            if key == "Q":
                break
            if key in "SPRE":
                bridge.parse({"cmd": {"S": "START", "P": "PAUSE", "R": "RESUME", "E": "STOP"}[key]})


if __name__ == "__main__":
    main()
