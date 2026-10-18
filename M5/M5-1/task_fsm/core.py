# -*- coding: utf-8 -*-
"""任务调度内核：读取 YAML -> 构建节点 -> 按状态转移执行。"""

from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from .context import TaskContext
from .logger import Logger
from .registry import Registry


class TaskRunner:
    """执行一次由 YAML 描述的比赛任务。

    重试采用“每步 retry 次数 + 可选全局 retry_budget”双保险；fallback 链同时
    受单节点访问次数与总跳转次数限制，避免配置错误造成死循环。
    """

    MAX_STEP_VISITS = 3
    MAX_FALLBACK_HOPS = 8
    DEFAULT_TIMEOUT = 60.0

    def __init__(self, task, ctx=None, registry=None, logger=None):
        self.task = task or {}
        deadline = task.get("deadline")
        if ctx is None:
            ctx = TaskContext(
                task_id=task.get("task_id"),
                deadline=(time.time() + float(deadline)) if deadline else None,
                retry_budget_total=task.get("retry_budget"),
            )
        else:
            if task.get("task_id"):
                ctx.task_id = task["task_id"]
            if deadline:
                ctx.deadline = time.time() + float(deadline)
            if task.get("retry_budget") is not None:
                ctx.retry_budget_total = int(task["retry_budget"])
        self.ctx = ctx
        self.registry = registry or Registry()
        self.logger = logger or Logger(color=True)
        self.specs = self._normalize(task.get("tasks") or task.get("steps") or [])
        self.report_steps: list[dict[str, Any]] = []
        self.visits: dict[str, int] = {}
        self.fallback_hops = 0

    def _normalize(self, raw):
        if not isinstance(raw, list):
            raise ValueError("tasks/steps 必须是列表")
        specs: list[dict[str, Any]] = []
        for index, item in enumerate(raw):
            if not isinstance(item, dict) or not item.get("name"):
                raise ValueError(f"第 {index + 1} 个步骤必须包含 name")
            if "parallel" not in item:
                self.registry.validate_type(item.get("type"))
            specs.append(dict(item))
        if len({s["name"] for s in specs}) != len(specs):
            raise ValueError("步骤 name 必须唯一")
        return specs

    def _index_by_name(self, name):
        return next((i for i, s in enumerate(self.specs) if s["name"] == name), None)

    def run(self):
        started = time.monotonic()
        if not self.specs:
            return self._report("SUCCESS", started)
        index, result = 0, "SUCCESS"
        while index < len(self.specs):
            if self.ctx.is_deadline_exceeded():
                result, index = "TIMEOUT", len(self.specs)
                break
            if self.ctx.aborted:
                result, index = "ABORTED", len(self.specs)
                break
            spec = self.specs[index]
            name = spec["name"]
            self.visits[name] = self.visits.get(name, 0) + 1
            if self.visits[name] > self.MAX_STEP_VISITS:
                self.logger.error(f"{name} 访问次数超限，疑似 fallback 死循环")
                result = "FAILED"
                break
            self.ctx.set_state(name, "RUNNING")
            step = self._execute_spec(spec)
            self.ctx.set_state(name, step["status"])
            self.report_steps.append(step)
            if step["status"] == "SUCCESS":
                index += 1
                continue
            if spec.get("on_fail") == "skip" and not spec.get("fallback"):
                index += 1
                continue
            target = self._index_by_name(spec.get("fallback")) if spec.get("fallback") else None
            if target is None or self.fallback_hops >= self.MAX_FALLBACK_HOPS:
                result = "FAILED"
                break
            self.fallback_hops += 1
            self.logger.warning(f"{name} 降级跳转到 {spec['fallback']}")
            index = target
        if index >= len(self.specs) and result == "SUCCESS":
            result = "SUCCESS"
        return self._report(result, started)

    def _execute_spec(self, spec):
        return self._run_parallel(spec) if "parallel" in spec else self._run_node(spec)

    def _run_node(self, spec):
        name = spec["name"]
        node = self.registry.create(name, spec, self.ctx)
        node.setup()
        timeout = float(spec.get("timeout", self.DEFAULT_TIMEOUT))
        retries, max_retries, outcome, timed_out = 0, int(spec.get("retry", 0)), "FAILED", False
        interval = float(spec.get("retry_interval", 1.0))
        started = time.monotonic()
        try:
            while True:
                box: dict[str, Any] = {}
                worker = threading.Thread(target=self._invoke_node, args=(node, box))
                worker.start()
                worker.join(timeout)
                if worker.is_alive():
                    timed_out = True
                    node.cancel()
                    worker.join(0.5)
                    outcome = "FAILED"
                else:
                    outcome = box.get("result", "FAILED")
                    timed_out = box.get("timed_out", False)
                if outcome == "SUCCESS" or self.ctx.aborted or self.ctx.cancel_event.is_set():
                    if outcome != "SUCCESS":
                        outcome = "SKIPPED"
                    break
                if retries < max_retries and self.ctx.can_retry():
                    self.ctx.consume_retry()
                    retries += 1
                    self.logger.log("RETRYING", f"{name} 重试 {retries}/{max_retries}")
                    time.sleep(interval)
                    if self.ctx.cancel_event.is_set():
                        outcome = "SKIPPED"
                        break
                    continue
                break
        finally:
            node.teardown()
        if outcome == "SUCCESS":
            status = "SUCCESS"
        elif spec.get("on_fail") == "skip" or spec.get("fallback"):
            status = "SKIPPED"
        else:
            status = "FAILED"
        self.logger.transition(name, "RUNNING", status)
        return {
            "name": name,
            "status": status,
            "elapsed_s": round(time.monotonic() - started, 3),
            "retries": retries,
            "degraded": status == "SKIPPED",
            "timed_out": timed_out,
        }

    def _invoke_node(self, node, box):
        try:
            box["result"] = node.execute()
        except TimeoutError:
            box["result"], box["timed_out"] = "FAILED", True
        except Exception as exc:
            box["result"], box["error"] = "FAILED", str(exc)

    def _run_parallel(self, spec):
        name = spec["name"]
        branches = spec.get("parallel", {}).get("branches", [])
        if not isinstance(branches, list) or not branches:
            raise ValueError(f"parallel 节点 {name} 至少需要一个 branch")
        started = time.monotonic()
        with ThreadPoolExecutor(max_workers=len(branches)) as pool:
            branch_reports = [f.result() for f in [pool.submit(self._execute_spec, b) for b in branches]]
        statuses = [b["status"] for b in branch_reports]
        status = "FAILED" if "FAILED" in statuses else ("SKIPPED" if "SKIPPED" in statuses else "SUCCESS")
        self.logger.transition(name, "RUNNING", status)
        return {
            "name": name,
            "status": status,
            "elapsed_s": round(time.monotonic() - started, 3),
            "retries": sum(b.get("retries", 0) for b in branch_reports),
            "degraded": status == "SKIPPED",
            "timed_out": any(b.get("timed_out") for b in branch_reports),
            "branches": branch_reports,
        }

    def _report(self, result, started):
        return {
            "task_id": self.ctx.task_id,
            "result": result,
            "total_elapsed_s": round(time.monotonic() - started, 3),
            "steps": self.report_steps,
            "final_context": self.ctx.snapshot(),
        }
