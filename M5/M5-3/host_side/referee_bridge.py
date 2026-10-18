# -*- coding: utf-8 -*-
"""裁判协议适配器：解析指令、维护状态、倒计时与模拟按键。"""

from __future__ import annotations

import json
import threading
import time
from typing import Any, Callable


class RefereeBridge:
    """订阅 /referee/cmd，发布 /referee/status。"""

    COMMANDS = {"START", "PAUSE", "RESUME", "STOP", "PENALTY", "SCORE_QUERY"}
    STATES = {"READY", "RUNNING", "PAUSED", "STOPPED", "FAULT"}

    def __init__(self, on_status: Callable[[dict[str, Any]], None], on_pause: Callable[[], None] | None = None, on_resume: Callable[[], None] | None = None) -> None:
        self.on_status = on_status
        self.on_pause = on_pause
        self.on_resume = on_resume
        self.state = "READY"
        self.countdown: float | None = None
        self.stage = ""
        self.penalty_records: list[dict[str, Any]] = []
        self._stop = threading.Event()

    def parse(self, message: Any) -> dict[str, Any]:
        if isinstance(message, (bytes, str)):
            try:
                cmd = json.loads(message)
            except json.JSONDecodeError:
                return self._status(error=f"非法指令: {message}")
        else:
            cmd = message
        op = str(cmd.get("cmd", "")).upper()
        if op not in self.COMMANDS:
            return self._status(error=f"未知指令: {op}")
        self._apply(op, cmd)
        return self.status()

    def _apply(self, op: str, cmd: dict[str, Any]) -> None:
        if op == "START":
            self.state = "RUNNING"
            self.countdown = float(cmd.get("countdown", 0))
            self.stage = str(cmd.get("stage", ""))
            self.penalty_records.clear()
        elif op == "PAUSE":
            self.state = "PAUSED"
            if self.on_pause:
                self.on_pause()
        elif op == "RESUME":
            self.state = "RUNNING"
            if self.on_resume:
                self.on_resume()
        elif op == "STOP":
            self.state = "STOPPED"
            self.countdown = None
        elif op == "PENALTY":
            self.state = "RUNNING"
            self.penalty_records.append({"ts": time.time(), "penalty_time": cmd.get("penalty_time", 0)})
        elif op == "SCORE_QUERY":
            pass

    def status(self) -> dict[str, Any]:
        return {
            "state": self.state,
            "countdown": self.countdown,
            "stage": self.stage,
            "penalties": self.penalty_records,
        }

    def _status(self, **extra) -> dict[str, Any]:
        out = self.status()
        out.update(extra)
        return out

    def emit_status(self) -> None:
        self.on_status(self.status())

    def keyboard_loop(self, key_fn: Callable[[], str | None] | None = None) -> None:
        """本地模拟：S=START P=PAUSE R=RESUME E=STOP。"""
        while not self._stop.is_set():
            key = key_fn() if key_fn else _read_key()
            if key:
                mapping = {"S": "START", "P": "PAUSE", "R": "RESUME", "E": "STOP"}
                if key.upper() in mapping:
                    self.parse({"cmd": mapping[key.upper()]})
            time.sleep(0.05)

    def stop(self) -> None:
        self._stop.set()


def _read_key() -> str | None:
    try:
        import msvcrt

        if msvcrt.kbhit():
            return msvcrt.getwch()
    except ImportError:
        import select
        import sys

        if select.select([sys.stdin], [], [], 0)[0]:
            return sys.stdin.read(1)
    return None
