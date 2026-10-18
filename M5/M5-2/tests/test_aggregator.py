# -*- coding: utf-8 -*-
"""聚合核心的轻量单测。"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "robot_side"))
from aggregator_core import DashboardAggregator  # noqa: E402


def test_metrics_and_fault_detection():
    published = []
    config = {
        "topic_patterns": ["/perception/**", "/hw/**"],
        "special_topics": {"task_state": "/task_state"},
        "publish": {"metrics_hz": 10},
        "fault_rules": {
            "freq_low": {"threshold_hz": 10, "duration_s": 2},
            "topic_timeout_s": 3,
            "cpu_high_pct": 85,
            "temp_high_c": 85,
            "voltage_low_v": 10.5,
        },
    }
    agg = DashboardAggregator(config, publish=lambda t, p: published.append((t, p)))
    agg.handle_message("/perception/camera", {"expected_hz": 20, "latency_ms": 3}, stamp=1.0)
    metrics = agg.collect_metrics()
    assert "/perception/camera" in metrics["topics"]
    assert metrics["topics"]["/perception/camera"]["count"] == 1


def test_task_state_publish():
    published = []
    config = {
        "topic_patterns": [],
        "special_topics": {"task_state": "/task_state"},
        "publish": {"metrics_hz": 10},
        "fault_rules": {},
    }
    agg = DashboardAggregator(config, publish=lambda t, p: published.append((t, p)))
    agg.handle_message("/task_state", {"current": "nav"}, stamp=1.0)
    assert published
    assert published[0][0] == "/dashboard/task_state"
