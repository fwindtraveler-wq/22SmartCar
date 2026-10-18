# -*- coding: utf-8 -*-
"""参数/场景/模型热切换，不重启节点。"""

from __future__ import annotations

import csv
import threading
import time
from pathlib import Path
from typing import Any, Callable


class HotSwitch:
    """热切换并记录审计与 switch_log.csv。

    loaders 是“资源名 -> 加载函数”的映射；加载失败会保留旧资源并返回错误，
    保证一次失败切换不会破坏正在运行的比赛。
    """

    def __init__(
        self,
        switch_log: str | Path,
        audit: Callable[[str, dict[str, Any]], None],
        loaders: dict[str, Callable[[Any], None]] | None = None,
    ) -> None:
        self.switch_log = Path(switch_log)
        self.audit = audit
        self.loaders = loaders or {}
        self._active: dict[str, Any] = {}
        self._lock = threading.Lock()
        if not self.switch_log.exists():
            self.switch_log.write_text("ts,kind,from,to,user,result\n", encoding="utf-8")

    def switch(self, kind: str, target: Any, user: str = "operator") -> dict[str, Any]:
        with self._lock:
            old = self._active.get(kind)
            loader = self.loaders.get(kind)
            try:
                if loader:
                    loader(target)
            except Exception as exc:
                self._record(kind, old, target, user, f"failed:{exc}")
                self.audit("SWITCH", kind=kind, from_value=old, to_value=target, user=user, result="fail")
                return {"ok": False, "reason": str(exc), "active": old}
            self._active[kind] = target
            self._record(kind, old, target, user, "ok")
            self.audit("SWITCH", kind=kind, from_value=old, to_value=target, user=user, result="ok")
            return {"ok": True, "from": old, "to": target}

    def set_param(self, name: str, value: Any, user: str = "operator") -> dict[str, Any]:
        return self.switch("param:" + name, value, user)

    def _record(self, kind: str, old: Any, new: Any, user: str, result: str) -> None:
        with self.switch_log.open("a", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow([time.time(), kind, old, new, user, result])
