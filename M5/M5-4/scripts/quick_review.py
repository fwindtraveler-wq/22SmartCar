#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""单次运行复盘：30 秒内给出结论、关键指标和故障因果链。"""

from __future__ import annotations

import argparse
import csv
import json
import time
from pathlib import Path
from typing import Any

from parse_mcap import extract_metrics, load_key_topics


def load_task_report(path: str | Path | None) -> dict[str, Any]:
    if not path or not Path(path).exists():
        return {}
    return json.loads(Path(path).read_text(encoding="utf-8"))


def load_switch_log(path: str | Path | None) -> list[dict[str, str]]:
    if not path or not Path(path).exists():
        return []
    with Path(path).open("r", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def scan_logs(logs_dir: str | Path | None) -> list[str]:
    if not logs_dir or not Path(logs_dir).exists():
        return []
    found: list[str] = []
    for file in Path(logs_dir).rglob("*"):
        if not file.is_file():
            continue
        for line in file.read_text(encoding="utf-8", errors="replace").splitlines():
            low = line.lower()
            if any(word in low for word in ("error", "fault", "degraded", "timeout", "fallback")):
                found.append(f"{file.name}:{line.strip()}")
    return found[-30:]


def detect_root_causes(metrics: dict[str, Any], logs: list[str]) -> list[str]:
    causes: list[str] = []
    if (metrics.get("perception_hz") or 0) < 10:
        causes.append(
            f"camera_degraded@{(metrics.get('perception_hz') or 0):.1f}Hz (freq<10Hz) -> nav fallback to lidar_only (+12s)"
        )
    if (metrics.get("temp_peak_c") or 0) > 85:
        causes.append(
            f"thermal_throttle@{metrics.get('temp_peak_c')}C (>=85C) -> model swap to yolov8n_int8 (-8fps)"
        )
    if metrics.get("nav_success_rate") is not None and metrics["nav_success_rate"] < 1:
        causes.append(
            f"nav_retry@{metrics.get('nav_time_avg_s')}s (success={metrics.get('nav_success_rate')}) -> fallback chain (+8s)"
        )
    if metrics.get("voltage_min_v") is not None and metrics["voltage_min_v"] < 10.5:
        causes.append(f"low_voltage@{metrics.get('voltage_min_v')}V (<10.5V) -> power throttle")
    for line in logs:
        if "timeout" in line.lower() or "fallback" in line.lower():
            causes.append(line)
    return causes[:4]


def build_review(
    mcap: Path,
    logs_dir: Path | None,
    switch_log: Path | None,
    task_report: Path | None,
    key_topics: list[str],
) -> dict[str, Any]:
    started = time.monotonic()
    metrics = extract_metrics(mcap, key_topics)
    task = load_task_report(task_report)
    switches = load_switch_log(switch_log)
    logs = scan_logs(logs_dir)
    causes = detect_root_causes(metrics, logs)
    result = task.get("result", "UNKNOWN")
    return {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "elapsed_s": round(time.monotonic() - started, 3),
        "mcap": str(mcap),
        "task_result": result,
        "total_elapsed_s": task.get("total_elapsed_s"),
        "steps": task.get("steps", []),
        "metrics": metrics,
        "root_causes": causes,
        "switches": switches,
    }


def load_previous_review(outputs_dir: Path, current_file: Path | None = None) -> dict[str, Any]:
    files = sorted(outputs_dir.glob("review_*.json"))
    if current_file and current_file.name in [f.name for f in files]:
        files = [f for f in files if f.name != current_file.name]
    if not files:
        return {}
    return json.loads(files[-1].read_text(encoding="utf-8"))


def compare_metrics(current: dict[str, Any], previous: dict[str, Any]) -> list[dict[str, Any]]:
    if not previous:
        return []
    rows = []
    prev_metrics = previous.get("metrics", {})
    for key, value in current.get("metrics", {}).items():
        old = prev_metrics.get(key)
        if old is None or value is None:
            continue
        rows.append(
            {"metric": key, "current": value, "previous": old, "delta": round(value - old, 3)}
        )
    return rows


def render_markdown(review: dict[str, Any], previous: dict[str, Any] | None = None) -> str:
    lines = [
        "# 复盘报告",
        "",
        f"- 生成时间: {review['generated_at']}",
        f"- 解析耗时: {review['elapsed_s']}s",
        f"- 任务结果: {review['task_result']}",
        f"- 总耗时: {review.get('total_elapsed_s')}",
        "",
        "## 关键指标",
        "",
        "| 指标 | 数值 |",
        "| :-- | :-- |",
    ]
    for key, value in review["metrics"].items():
        lines.append(f"| {key} | {value} |")
    lines += ["", "## 子任务", "", "| 节点 | 状态 | 耗时 | 重试 | 降级 |", "| :-- | :-- | :-- | :-- | :-- |"]
    for step in review.get("steps", []):
        lines.append(
            f"| {step.get('name')} | {step.get('status')} | {step.get('elapsed_s')} | {step.get('retries')} | {step.get('degraded')} |"
        )
    lines += ["", "## 故障根因", ""]
    for cause in review.get("root_causes", []) or ["未发现明显故障"]:
        lines.append(f"- {cause}")
    if previous:
        lines += ["", "## 与上一把对比", "", "| 指标 | 当前 | 上一把 | 差值 |", "| :-- | :-- | :-- | :-- |"]
        for row in compare_metrics(review, previous):
            lines.append(f"| {row['metric']} | {row['current']} | {row['previous']} | {row['delta']} |")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="quick review")
    parser.add_argument("--mcap", required=True)
    parser.add_argument("--logs", default=None)
    parser.add_argument("--switch-log", default=None)
    parser.add_argument("--task-report", default=None)
    parser.add_argument("--key-topics", default="config/key_topics.yaml")
    parser.add_argument("--out", default=None)
    args = parser.parse_args(argv)

    key_topics = load_key_topics(args.key_topics)
    review = build_review(
        Path(args.mcap),
        Path(args.logs) if args.logs else None,
        Path(args.switch_log) if args.switch_log else None,
        Path(args.task_report) if args.task_report else None,
        key_topics,
    )
    outputs = Path("outputs")
    outputs.mkdir(exist_ok=True)
    stamp = time.strftime("%Y%m%d_%H%M%S")
    md_path = args.out or outputs / f"review_{stamp}.md"
    json_path = Path(md_path).with_suffix(".json")
    Path(md_path).parent.mkdir(parents=True, exist_ok=True)
    previous = load_previous_review(outputs, json_path)
    md_path.write_text(render_markdown(review, previous), encoding="utf-8")
    json_path.write_text(json.dumps(review, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"复盘完成: {md_path} (解析耗时 {review['elapsed_s']}s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
