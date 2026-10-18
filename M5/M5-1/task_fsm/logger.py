# -*- coding: utf-8 -*-
"""终端彩色日志，便于现场快速判断状态迁移、重试、降级和超时。"""

from __future__ import annotations

import sys
from datetime import datetime


class Logger:
    """使用 ANSI 颜色区分事件类型，输出统一时间戳。"""

    COLORS = {
        "RESET": "\033[0m",
        "IDLE": "\033[90m",
        "RUNNING": "\033[36m",
        "SUCCESS": "\033[32m",
        "FAILED": "\033[31m",
        "SKIPPED": "\033[33m",
        "RETRYING": "\033[35m",
        "TIMEOUT": "\033[31m",
        "DEGRADED": "\033[33m",
    }

    def __init__(self, color: bool = True) -> None:
        self.color = color and sys.stdout.isatty()

    def _fmt(self, color: str, text: str) -> str:
        if not self.color:
            return text
        return f"{self.COLORS[color]}{text}{self.COLORS['RESET']}"

    def log(self, level: str, message: str) -> None:
        color = self.COLORS.get(level, "RESET")
        stamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        print(f"[{stamp}] {self._fmt(color, f'[{level:<8}]')} {message}", flush=True)

    def info(self, message: str) -> None:
        self.log("RUNNING", message)

    def success(self, message: str) -> None:
        self.log("SUCCESS", message)

    def warning(self, message: str) -> None:
        self.log("SKIPPED", message)

    def error(self, message: str) -> None:
        self.log("FAILED", message)

    def transition(self, node: str, old: str, new: str) -> None:
        self.log(new, f"{node}: {old} -> {new}")
