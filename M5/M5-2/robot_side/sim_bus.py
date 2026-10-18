# -*- coding: utf-8 -*-
"""用于测试和本地演示的内存总线，不依赖 ROS2。"""

from __future__ import annotations

import threading
import time
from typing import Any, Callable


class SimBus:
    """模拟一个话题总线，方便把真实 ROS 适配层与聚合核心解耦。"""

    def __init__(self) -> None:
        self._subs: list[tuple[Callable[[str, bool], bool], Callable[[str, Any, float], None]]] = []
        self._lock = threading.Lock()

    def publish(self, topic: str, message: Any, stamp: float | None = None) -> None:
        now = stamp or time.time()
        with self._lock:
            subs = list(self._subs)
        for matcher, callback in subs:
            if matcher(topic, False):
                callback(topic, message, now)

    def subscribe(self, pattern: str, callback: Callable[[str, Any, float], None]) -> None:
        def matcher(topic: str, _: bool) -> bool:
            pat = pattern.replace("**", "*")
            import fnmatch

            return fnmatch.fnmatchcase(topic, pat)

        with self._lock:
            self._subs.append((matcher, callback))
