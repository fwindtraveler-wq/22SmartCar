# -*- coding: utf-8 -*-
"""调度内核级单测：重试、fallback、超时与并行分支。"""

from __future__ import annotations

from task_fsm.context import TaskContext
from task_fsm.core import TaskRunner
from task_fsm.registry import Registry


def _success_node(name, params, ctx):
    class Node:
        def __init__(self, name, params, ctx):
            self.name, self.params, self.ctx = name, params, ctx

        def setup(self):
            pass

        def execute(self):
            return params.get("result", "SUCCESS")

        def cancel(self):
            pass

        def teardown(self):
            pass

    return Node(name, params, ctx)


def test_retry_then_success():
    state = {"n": 0}

    def callback(payload):
        state["n"] += 1
        return {"status": "SUCCESS" if state["n"] == 3 else "FAILED"}

    ctx = TaskContext(service_callbacks={"navigate_to_pose": callback})
    task = {
        "tasks": [
            {
                "name": "nav",
                "type": "NavigateTo",
                "pose": {"x": 0, "y": 0},
                "retry": 2,
                "retry_interval": 0.01,
                "timeout": 1,
            }
        ]
    }
    report = TaskRunner(task, ctx=ctx).run()
    assert report["result"] == "SUCCESS"
    assert report["steps"][0]["retries"] == 2


def test_retry_exhausted_then_fallback():
    ctx = TaskContext(
        service_callbacks={
            "navigate_to_pose": lambda p: {"status": "FAILED"},
            "tts_speak": lambda p: {"status": "SUCCESS"},
        }
    )
    task = {
        "tasks": [
            {
                "name": "nav",
                "type": "NavigateTo",
                "pose": {"x": 0, "y": 0},
                "retry": 1,
                "retry_interval": 0.01,
                "fallback": "tts",
            },
            {"name": "tts", "type": "SpeakTTS", "text": "fallback"},
        ]
    }
    report = TaskRunner(task, ctx=ctx).run()
    assert report["result"] == "SUCCESS"
    assert report["steps"][0]["status"] == "SKIPPED"


def test_parallel_any_fail():
    registry = Registry()

    class Always:
        def __init__(self, name, params, ctx):
            self.name, self.params, self.ctx = name, params, ctx

        def setup(self):
            pass

        def execute(self):
            return self.params.get("result", "SUCCESS")

        def cancel(self):
            pass

        def teardown(self):
            pass

    registry.register("Mock", Always)
    task = {
        "tasks": [
            {
                "name": "parallel",
                "parallel": {
                    "fail_policy": "any_fail",
                    "branches": [
                        {"name": "a", "type": "Mock", "result": "SUCCESS"},
                        {"name": "b", "type": "Mock", "result": "FAILED"},
                    ],
                },
            }
        ]
    }
    report = TaskRunner(task, ctx=TaskContext(), registry=registry).run()
    assert report["result"] == "FAILED"
