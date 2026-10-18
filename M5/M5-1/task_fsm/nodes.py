# -*- coding: utf-8 -*-
"""五个标准任务节点。

所有节点都通过 TaskContext 中注入的回调访问外部能力，因此可以在单测中
用假 Action、假 Service 和假主题快照替换，完全不依赖 ROS2 运行时。
"""

from __future__ import annotations

import select
import sys
import time
from typing import Any

try:
    import msvcrt
except ImportError:  # 在 Linux/macOS 上运行时不依赖 Windows 控制台 API
    msvcrt = None


def _key_pressed(key: str = " ") -> bool:
    """非阻塞检测键盘按键，供 WaitForTrigger 使用。"""
    if msvcrt is not None:
        if msvcrt.kbhit():
            return msvcrt.getch() in (key.encode(), b" ")
        return False
    if select.select([sys.stdin], [], [], 0)[0]:
        try:
            return sys.stdin.read(1) == key
        except Exception:
            return False
    return False


def _await_call(call: Any, ctx, timeout: float):
    """等待可能是 Future 对象或普通结果的调用完成。"""
    deadline = time.monotonic() + timeout
    current = call
    while time.monotonic() < deadline and not ctx.cancel_event.is_set():
        if hasattr(current, "done") and callable(current.done):
            if current.done():
                return current.result()
            time.sleep(0.02)
            continue
        return current
    if ctx.cancel_event.is_set():
        raise InterruptedError("任务已取消")
    raise TimeoutError("调用超时")


class TaskNode:
    """节点基类，接口固定为 setup/execute/cancel/teardown。"""

    def __init__(self, name: str, params: dict, ctx) -> None:
        self.name = name
        self.params = params
        self.ctx = ctx
        self.cancelled = False

    def setup(self) -> None:
        """可选资源准备。"""

    def execute(self) -> str:
        raise NotImplementedError

    def cancel(self) -> None:
        """协作式取消，调用后 execute 应尽快退出。"""
        self.cancelled = True

    def teardown(self) -> None:
        """可选资源释放。"""

    def _cancelled(self) -> bool:
        return self.cancelled or self.ctx.cancel_event.is_set()

    def _progress(self, percent: int, message: str) -> None:
        self.ctx.report_progress(self.name, percent, message)


class WaitForTrigger(TaskNode):
    """等待裁判开始指令或本地空格键，超时视为失败。"""

    def execute(self) -> str:
        timeout = float(self.params.get("timeout", 30))
        deadline = time.monotonic() + timeout
        self._progress(0, "等待开始触发")
        while time.monotonic() < deadline:
            if self._cancelled():
                return "SKIPPED"
            if self.ctx.trigger_event.is_set() or self.ctx.data.get("trigger"):
                self._progress(100, "收到触发")
                return "SUCCESS"
            if self.params.get("keyboard", True) and _key_pressed(" "):
                self._progress(100, "收到键盘空格")
                return "SUCCESS"
            time.sleep(0.05)
        return "FAILED"


class NavigateTo(TaskNode):
    """调用导航 Action，并把结果写入上下文。"""

    def _target_pose(self) -> Any:
        if self.params.get("pose_from_context"):
            key = self.params["pose_from_context"]
            return self.ctx.data.get(key, self.params.get("pose"))
        return self.params.get("pose")

    def execute(self) -> str:
        pose = self._target_pose()
        if pose is None:
            return "FAILED"
        self._progress(10, "下发导航目标")
        try:
            call = self.ctx.invoke("navigate_to_pose", {"pose": pose})
            result = _await_call(call, self.ctx, float(self.params.get("timeout", 30)))
        except Exception:
            return "FAILED"
        self.ctx.data["last_nav_result"] = result
        self.ctx.data["last_nav_pose"] = pose
        status = result if isinstance(result, str) else result.get("status", "SUCCESS")
        self._progress(100, f"导航结果: {status}")
        return "SUCCESS" if status in ("SUCCESS", "ok", 0, True) else "FAILED"


class DetectTarget(TaskNode):
    """订阅感知目标，等待指定类别和置信度达标。"""

    def execute(self) -> str:
        target_class = self.params.get("target_class", "*")
        min_conf = float(self.params.get("min_confidence", 0.5))
        timeout = float(self.params.get("timeout", 15))
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline and not self._cancelled():
            try:
                targets = self.ctx.read_topic("perception_targets")
            except Exception:
                time.sleep(0.05)
                continue
            for target in targets or []:
                cls_ok = target_class == "*" or target.get("class") == target_class
                conf = float(target.get("confidence", 0.0))
                if cls_ok and conf >= min_conf:
                    self.ctx.data["target_pose"] = target.get("pose")
                    self.ctx.data["target_id"] = target.get("id")
                    self._progress(100, f"检测到 {target.get('id')}")
                    return "SUCCESS"
            time.sleep(0.05)
        return "SKIPPED" if self._cancelled() else "FAILED"


class ExecuteGrasp(TaskNode):
    """调用抓取 Action，并记录抓取结果与物体位姿。"""

    def execute(self) -> str:
        payload = {
            "grasp_pose": self.params.get("grasp_pose") or self.ctx.data.get("target_pose"),
            "grasp_type": self.params.get("grasp_type", "top_down"),
        }
        try:
            call = self.ctx.invoke("manipulation_grasp", payload)
            result = _await_call(call, self.ctx, float(self.params.get("timeout", 20)))
        except Exception:
            return "FAILED"
        self.ctx.data["grasp_result"] = result
        self.ctx.data["object_pose"] = (
            result.get("object_pose") if isinstance(result, dict) else payload["grasp_pose"]
        )
        status = result if isinstance(result, str) else result.get("status", "SUCCESS")
        return "SUCCESS" if status in ("SUCCESS", "ok", 0, True) else "FAILED"


class SpeakTTS(TaskNode):
    """调用 TTS Service 播放指定文本。"""

    def execute(self) -> str:
        text = self.params.get("text", "")
        try:
            call = self.ctx.invoke("tts_speak", {"text": text})
            result = _await_call(call, self.ctx, float(self.params.get("timeout", 10)))
        except Exception:
            return "FAILED"
        status = result if isinstance(result, str) else result.get("status", "SUCCESS")
        return "SUCCESS" if status in ("SUCCESS", "ok", 0, True) else "FAILED"
