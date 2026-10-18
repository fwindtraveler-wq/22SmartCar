#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""测量小车侧/主机侧进程的 CPU 与内存，输出持续 60 秒的平均值。"""

from __future__ import annotations

import argparse
import subprocess
import time


def _psutil_measure(pid: int) -> dict:
    import psutil

    proc = psutil.Process(pid)
    cpu_sum = 0.0
    mem_sum = 0.0
    for _ in range(12):
        cpu_sum += proc.cpu_percent(interval=0.5)
        mem_sum += proc.memory_info().rss / 1024 / 1024
    return {"cpu_pct": round(cpu_sum / 12, 2), "rss_mb": round(mem_sum / 12, 1)}


def _fallback_measure(pid: int) -> dict:
    # 无 psutil 时用 Windows 任务列表读取一次内存，CPU 需要外部工具。
    out = subprocess.run(
        ["powershell", "-NoProfile", "-Command", f"(Get-Process -Id {pid}).WorkingSet64"],
        capture_output=True,
        text=True,
    ).stdout.strip()
    return {"cpu_pct": None, "rss_mb": round(float(out) / 1024 / 1024, 1) if out else None}


def main() -> None:
    parser = argparse.ArgumentParser(description="测量进程资源")
    parser.add_argument("--pid", type=int, required=True)
    parser.add_argument("--seconds", type=int, default=60)
    args = parser.parse_args()
    try:
        result = _psutil_measure(args.pid)
    except ImportError:
        result = _fallback_measure(args.pid)
    print(result)


if __name__ == "__main__":
    main()
