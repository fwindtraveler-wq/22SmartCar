# -*- coding: utf-8 -*-
"""复盘与选择性解析的单测。"""

from __future__ import annotations

import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPT))
from parse_mcap import extract_metrics  # noqa: E402
from quick_review import build_review  # noqa: E402


def test_extract_metrics_from_jsonl_sample():
    metrics = extract_metrics(
        SCRIPT.parent / "data" / "run_01.mcap",
        ["/perception/**", "/navigation/**", "/hw/**"],
    )
    assert metrics["nav_success_rate"] is not None
    assert metrics["temp_peak_c"] >= 85


def test_build_review_has_root_causes():
    review = build_review(
        SCRIPT.parent / "data" / "run_01.mcap",
        SCRIPT.parent / "data" / "logs",
        SCRIPT.parent / "data" / "switch_log.csv",
        SCRIPT.parent / "data" / "task_report.json",
        ["/perception/**", "/navigation/**", "/hw/**"],
    )
    assert review["task_result"] in ("SUCCESS", "FAILED", "TIMEOUT")
    assert review["root_causes"]
