#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""选择性解析 MCAP：只挑关键话题，避免全量解析导致复盘超时。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterator

from yamlmini import load_yaml


def load_key_topics(path: str | Path = "config/key_topics.yaml") -> list[str]:
    data = load_yaml(path) or {}
    return list(data.get("key_topics", []))


def iter_key_messages(mcap_path: str | Path, key_topics: list[str]) -> Iterator[dict[str, Any]]:
    """优先使用 mcap 库读取真实文件；缺失时支持 JSON Lines 样本。"""
    path = Path(mcap_path)
    if path.exists():
        with path.open("r", encoding="utf-8", errors="replace") as probe:
            first = probe.read(1)
        if first in ("{", "["):
            yield from _iter_jsonl_fallback(path, key_topics)
            return
    try:
        from mcap.reader import make_reader  # type: ignore
    except ImportError:
        yield from _iter_jsonl_fallback(path, key_topics)
        return

    with path.open("rb") as fh:
        reader = make_reader(fh)
        for schema, channel, message in reader.iter_messages():
            topic = channel.topic
            if not any(_match(p, topic) for p in key_topics):
                continue
            decoded = message.data.decode("utf-8", errors="replace")
            try:
                value = json.loads(decoded)
            except json.JSONDecodeError:
                value = decoded
            yield {
                "timestamp": float(message.log_time) / 1e9,
                "topic": topic,
                "value": value,
            }


def _iter_jsonl_fallback(path: Path, key_topics: list[str]) -> Iterator[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"MCAP 文件不存在: {path}")
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"MCAP 样本行不是合法 JSON: {exc}") from exc
            if any(_match(p, record.get("topic", "")) for p in key_topics):
                yield record


def _match(pattern: str, topic: str) -> bool:
    import fnmatch

    return fnmatch.fnmatchcase(topic, pattern.replace("**", "*"))


def extract_metrics(mcap_path: str | Path, key_topics: list[str]) -> dict[str, Any]:
    """把关键话题聚合成少量复盘指标。"""
    nav_count = 0
    nav_success = 0
    nav_time_sum = 0.0
    path_dev = 0.0
    conf_sum = 0.0
    conf_count = 0
    perf_count = 0
    perf_span = 0.0
    perf_first = None
    perf_last = None
    cpu_peak = 0.0
    temp_peak = 0.0
    volt_min = 1e9

    for msg in iter_key_messages(mcap_path, key_topics):
        topic = msg["topic"]
        value = msg["value"] if isinstance(msg["value"], dict) else {}
        ts = float(msg.get("timestamp", 0))
        if "navigation" in topic and ("result" in topic or "status" in topic):
            nav_count += 1
            if value.get("status") in ("SUCCESS", "ok", True):
                nav_success += 1
            nav_time_sum += float(value.get("elapsed_s", 0))
            path_dev = max(path_dev, float(value.get("path_deviation", 0)))
        if "perception" in topic:
            if perf_first is None:
                perf_first = ts
            perf_last = ts
            perf_count += 1
            conf_sum += float(value.get("confidence", 0))
        if "cpu" in topic:
            cpu_peak = max(cpu_peak, float(value.get("percent", 0)))
        if "temp" in topic:
            temp_peak = max(temp_peak, float(value.get("temperature", 0)))
        if "voltage" in topic or "battery" in topic:
            volt_min = min(volt_min, float(value.get("voltage", 1e9)))

    perf_span = max(0.0, (perf_last or 0) - (perf_first or 0))
    return {
        "nav_success_rate": round(nav_success / nav_count, 3) if nav_count else None,
        "nav_time_avg_s": round(nav_time_sum / nav_count, 3) if nav_count else None,
        "path_deviation_m": round(path_dev, 3),
        "perception_hz": round(perf_count / perf_span, 2) if perf_span > 0 else 0.0,
        "confidence_avg": round(conf_sum / conf_count, 3) if conf_count else None,
        "cpu_peak_pct": round(cpu_peak, 1),
        "temp_peak_c": round(temp_peak, 1),
        "voltage_min_v": round(volt_min, 2) if volt_min < 1e9 else None,
    }
