# -*- coding: utf-8 -*-
"""五个标准节点的 Mock 单测，不依赖 ROS2。"""

from __future__ import annotations

import time
from concurrent.futures import Future

from task_fsm.context import TaskContext
from task_fsm.nodes import DetectTarget, ExecuteGrasp, NavigateTo, SpeakTTS, WaitForTrigger


def _ctx(**overrides):
    return TaskContext(**overrides)


def _future(result):
    f = Future()
    f.set_result(result)
    return f


def test_wait_for_trigger_receives_event():
    ctx = _ctx()
    ctx.trigger_event.set()
    node = WaitForTrigger("wait", {"timeout": 1}, ctx)
    assert node.execute() == "SUCCESS"


def test_wait_for_trigger_timeout():
    ctx = _ctx()
    node = WaitForTrigger("wait", {"timeout": 0.02, "keyboard": False}, ctx)
    assert node.execute() == "FAILED"


def test_navigate_to_success():
    ctx = _ctx(service_callbacks={"navigate_to_pose": lambda p: _future({"status": "SUCCESS"})})
    node = NavigateTo("nav", {"pose": {"x": 1, "y": 2}, "timeout": 1}, ctx)
    assert node.execute() == "SUCCESS"
    assert ctx.data["last_nav_result"]["status"] == "SUCCESS"


def test_navigate_to_timeout():
    ctx = _ctx(service_callbacks={"navigate_to_pose": lambda p: _future({"status": "SUCCESS"})})
    node = NavigateTo("nav", {"pose": {"x": 1, "y": 2}, "timeout": 0}, ctx)
    assert node.execute() == "FAILED"


def test_detect_target_threshold():
    ctx = _ctx(
        topic_snapshot={
            "perception_targets": lambda: [
                {"class": "qrcode", "confidence": 0.8, "id": "qr_01", "pose": [1, 2]}
            ]
        }
    )
    node = DetectTarget("detect", {"target_class": "qrcode", "min_confidence": 0.7}, ctx)
    assert node.execute() == "SUCCESS"
    assert ctx.data["target_id"] == "qr_01"


def test_detect_target_low_confidence_timeout():
    ctx = _ctx(
        topic_snapshot={
            "perception_targets": lambda: [
                {"class": "qrcode", "confidence": 0.5, "id": "qr_01", "pose": [1, 2]}
            ]
        }
    )
    node = DetectTarget("detect", {"target_class": "qrcode", "min_confidence": 0.7, "timeout": 0.02}, ctx)
    assert node.execute() == "FAILED"


def test_grasp_success_and_retry():
    attempts = {"n": 0}

    def service(payload):
        attempts["n"] += 1
        return _future({"status": "SUCCESS" if attempts["n"] == 2 else "FAILED"})

    ctx = _ctx(service_callbacks={"manipulation_grasp": service})
    node = ExecuteGrasp("grasp", {"retry": 1}, ctx)
    # 单节点自身不负责重试，重试由调度器完成；这里验证首次失败会返回 FAILED。
    assert node.execute() == "FAILED"


def test_speak_tts_service_missing():
    ctx = _ctx()
    node = SpeakTTS("tts", {"text": "hi"}, ctx)
    assert node.execute() == "FAILED"
