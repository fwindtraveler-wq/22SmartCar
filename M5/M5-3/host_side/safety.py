# -*- coding: utf-8 -*-
"""分层紧急停车，禁止停车后自动恢复。"""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import Any, Callable


class SafetyController:
    """四层安全兜底：指令层、话题层、控制器层、记录层。"""

    def __init__(
        self,
        blackbox: str | Path,
        audit: Callable[[str, dict[str, Any]], None],
        publish: Callable[[str, Any], None],
        controller_estop: Callable[[], None] | None = None,
    ) -> None:
        self.blackbox = Path(blackbox)
        self.audit = audit
        self.publish = publish
        self.controller_estop = controller_estop or (lambda: None)
        self._lock = threading.Lock()
        self._stopped = False
        self._reason = ""

    def emergency_stop(self, reason: str, source: str = "ui", user: str = "operator") -> dict[str, Any]:
        with self._lock:
            if self._stopped:
                return {"ok": True, "already_stopped": True}
            self._stopped = True
            self._reason = reason
            # 层 1：下发零速度。
            self.publish("/cmd_vel", {"linear": 0.0, "angular": 0.0})
            # 层 2：让底盘订阅 /emergency_stop，自己进入锁存急停状态。
            self.publish("/emergency_stop", {"active": True, "reason": reason})
            # 层 3：触发控制器软急停。
            self.controller_estop()
            # 层 4：写黑匣子与审计。
            self._write_blackbox(reason)
            self.audit("EMERGENCY_STOP", reason=reason, source=source, user=user, result="ok")
            return {"ok": True, "reason": reason}

    def is_stopped(self) -> bool:
        return self._stopped

    def reset(self, user: str = "operator", confirm: bool = False) -> dict[str, Any]:
        if not confirm:
            return {"ok": False, "reason": "急停解除必须显式二次确认"}
        with self._lock:
            if not self._stopped:
                return {"ok": True, "already_reset": True}
            self._stopped = False
            self._reason = ""
            self.publish("/emergency_stop", {"active": False, "reason": "manual_reset"})
            self.audit("EMERGENCY_RESET", user=user, source="ui", result="ok")
            return {"ok": True}

    def _write_blackbox(self, reason: str) -> None:
        record = {"ts": time.time(), "reason": reason, "cmd_vel_zero": True}
        self.blackbox.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")
