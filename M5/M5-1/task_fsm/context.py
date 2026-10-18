# -*- coding: utf-8 -*-
"""任务执行上下文。

该对象贯穿一次任务的整个生命周期，承载共享数据、取消信号、任务截止时间、
重试预算以及供复盘使用的元数据。节点不应直接读取 YAML，参数由调度器传入。
"""

from __future__ import annotations

import threading
import time
import uuid
from typing import Any, Callable, Dict, Optional


class TaskContext:
    """任务级共享上下文。

    属性：
        task_id: 本次任务的唯一编号。
        deadline: 整体截止时间，超过后任务将被判为 TIMEOUT。
        data: 节点间共享的数据字典，例如目标位姿、识别结果。
        cancel_event: 协作式取消信号。节点应周期性检查它，收到后尽快退出。
        retry_budget_total: 可选的全局重试预算；与每步重试次数共同约束执行。
    """

    def __init__(
        self,
        task_id: Optional[str] = None,
        deadline: Optional[float] = None,
        retry_budget_total: Optional[int] = None,
        service_callbacks: Optional[Dict[str, Callable[..., Any]]] = None,
        topic_snapshot: Optional[Dict[str, Callable[[], Any]]] = None,
    ) -> None:
        self.task_id = task_id or self._make_task_id()
        self.deadline = deadline
        self.created_at = time.time()
        self.data: Dict[str, Any] = {}
        self.metadata: Dict[str, Any] = {}
        self.step_states: Dict[str, str] = {}

        # 取消采用协作式 Event，而不是强杀线程，因此节点能够安全释放资源。
        self.cancel_event = threading.Event()
        self.abort_reason: Optional[str] = None
        self.aborted = False

        # 全局重试预算用于兜底，防止某个 YAML 配置无限重试拖垮整场比赛。
        self.retry_budget_total = retry_budget_total
        self.retry_budget_used = 0

        # 通过回调注入外部能力，使节点可以脱离 ROS2 单测。
        self.service_callbacks = service_callbacks or {}
        self.topic_snapshot = topic_snapshot or {}
        self.trigger_event = threading.Event()
        self.progress_hooks: list[Callable[[str, int, str], None]] = []

    @staticmethod
    def _make_task_id() -> str:
        return "task_" + time.strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:6]

    def is_deadline_exceeded(self) -> bool:
        if self.deadline is None:
            return False
        return time.time() > self.deadline

    def remaining_seconds(self) -> Optional[float]:
        if self.deadline is None:
            return None
        return max(0.0, self.deadline - time.time())

    def set_state(self, step_name: str, state: str) -> None:
        self.step_states[step_name] = state

    def can_retry(self) -> bool:
        if self.retry_budget_total is None:
            return True
        return self.retry_budget_used < self.retry_budget_total

    def consume_retry(self) -> bool:
        if not self.can_retry():
            return False
        self.retry_budget_used += 1
        return True

    def invoke(self, service: str, payload: Any = None) -> Any:
        """调用注入的服务回调，节点无需关心 ROS2 Action/Service 的细节。"""
        callback = self.service_callbacks.get(service)
        if callback is None:
            raise KeyError(f"未注册服务: {service}")
        return callback(payload)

    def read_topic(self, topic: str) -> Any:
        """读取一次主题快照，便于在单测中注入假数据。"""
        callback = self.topic_snapshot.get(topic)
        if callback is None:
            raise KeyError(f"未注册主题快照: {topic}")
        return callback()

    def report_progress(self, step_name: str, percent: int, message: str) -> None:
        """上报中间进度，长任务可借此向界面展示更多信息。"""
        for hook in self.progress_hooks:
            hook(step_name, percent, message)

    def cancel(self, reason: str = "cancelled") -> None:
        self.abort_reason = reason
        self.cancel_event.set()

    def abort(self, reason: str) -> None:
        self.aborted = True
        self.cancel(reason)

    def snapshot(self) -> Dict[str, Any]:
        """生成最终上下文副本，写入 task_report.json 供下游复盘。"""
        return {
            "task_id": self.task_id,
            "data": dict(self.data),
            "metadata": dict(self.metadata),
            "abort_reason": self.abort_reason,
        }
