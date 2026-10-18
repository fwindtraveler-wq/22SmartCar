# -*- coding: utf-8 -*-
"""轻量聚合核心：只做聚合、降频和故障判定，不负责渲染与存储。"""

from __future__ import annotations

import fnmatch
import json
import threading
import time
from collections import defaultdict
from typing import Any, Callable


def topic_matches(pattern: str, topic: str) -> bool:
    """支持 ROS 风格通配符；** 转为 * 后按 glob 匹配。"""
    pat = pattern.replace("**", "*")
    return fnmatch.fnmatchcase(topic, pat)


class DashboardAggregator:
    """从原始话题采样到 /dashboard/* 聚合输出的核心逻辑。

    该对象不直接依赖 ROS2，测试时可用 SimBus 注入消息，部署时由
    dashboard_aggregator.py 的 ROS2 适配层负责订阅真实话题。
    """

    def __init__(
        self,
        config: dict[str, Any],
        publish: Callable[[str, Any], None],
        on_fault: Callable[[dict[str, Any]], None] | None = None,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self.config = config
        self.publish = publish
        self.on_fault = on_fault
        self.clock = clock
        self.patterns = list(config.get("topic_patterns", []))
        self.special = config.get("special_topics", {})
        self.fault_rules = config.get("fault_rules", {})
        self.metrics_hz = float(config.get("publish", {}).get("metrics_hz", 10))

        # 每个话题的聚合状态，只在收到原始消息时更新，不在主机端重新计算。
        self.topic_stats: dict[str, dict[str, Any]] = defaultdict(
            lambda: {"count": 0, "first_ts": None, "last_ts": None, "sum": 0.0, "values": []}
        )
        self.system_metrics: dict[str, Any] = {}
        self.task_state: dict[str, Any] = {}
        self.faults: dict[str, dict[str, Any]] = {}
        self._stop = threading.Event()
        self._lock = threading.Lock()

    def handle_message(self, topic: str, message: Any, stamp: float | None = None) -> None:
        """供 ROS 适配层或 SimBus 调用的统一入口。"""
        now = stamp if stamp is not None else self.clock()
        if not self._interested(topic):
            return
        if topic == self.special.get("task_state"):
            self._update_task_state(message)
            return
        with self._lock:
            stat = self.topic_stats[topic]
            stat["count"] += 1
            stat["last_ts"] = now
            if stat["first_ts"] is None:
                stat["first_ts"] = now
            stat["last_value"] = message
            self._consume_system_metric(topic, message)

    def _interested(self, topic: str) -> bool:
        if topic in self.special.values():
            return True
        return any(topic_matches(p, topic) for p in self.patterns)

    def _update_task_state(self, message: Any) -> None:
        self.task_state = self._as_dict(message)
        self.publish("/dashboard/task_state", self.task_state)

    def _consume_system_metric(self, topic: str, message: Any) -> None:
        if topic.endswith("/cpu") or "cpu" in topic.lower():
            self.system_metrics["cpu"] = self._number(message)
        elif "temp" in topic.lower():
            self.system_metrics["temp"] = self._number(message)
        elif "voltage" in topic.lower() or "battery" in topic.lower():
            self.system_metrics["voltage"] = self._number(message)
        elif "rtt" in topic.lower() or "network" in topic.lower():
            self.system_metrics["rtt"] = self._number(message)

    @staticmethod
    def _as_dict(value: Any) -> dict[str, Any]:
        if isinstance(value, dict):
            return value
        if isinstance(value, str):
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return {"text": value}
        return {"value": value}

    @staticmethod
    def _number(value: Any) -> float:
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, dict):
            for key in ("data", "value", "percent", "temperature", "voltage"):
                if key in value:
                    return DashboardAggregator._number(value[key])
        if isinstance(value, str):
            try:
                return float(value)
            except ValueError:
                return 0.0
        return 0.0

    def collect_metrics(self) -> dict[str, Any]:
        """把原始话题聚合为低带宽指标，供 /dashboard/metrics 使用。"""
        now = self.clock()
        per_topic: dict[str, Any] = {}
        with self._lock:
            for topic, stat in self.topic_stats.items():
                count = stat["count"]
                first, last = stat["first_ts"], stat["last_ts"]
                span = max(0.0, (last or now) - (first or now))
                freq = count / span if span > 0 else 0.0
                last_value = stat.get("last_value") or {}
                expected = float(last_value.get("expected_hz", 0) if isinstance(last_value, dict) else 0)
                latency = float(last_value.get("latency_ms", 0) if isinstance(last_value, dict) else 0)
                per_topic[topic] = {
                    "count": count,
                    "hz": round(freq, 2),
                    "latency_ms": round(latency, 3),
                    "drop_rate": round(max(0.0, 1.0 - freq / expected), 4) if expected else 0.0,
                    "last_value": stat.get("last_value"),
                }
        metrics = {
            "ts": now,
            "topics": per_topic,
            "system": dict(self.system_metrics),
            "task_state": self.task_state,
        }
        return metrics

    def evaluate_faults(self) -> list[dict[str, Any]]:
        """在小车端按规则判断故障，主机端只负责展示。"""
        now = self.clock()
        rules = self.fault_rules
        timeout = float(rules.get("topic_timeout_s", 3.0))
        low_hz = float(rules.get("freq_low", {}).get("threshold_hz", 10.0))
        low_duration = float(rules.get("freq_low", {}).get("duration_s", 2.0))
        events: list[dict[str, Any]] = []

        with self._lock:
            stats = {k: dict(v) for k, v in self.topic_stats.items()}
        for topic, stat in stats.items():
            last = stat.get("last_ts")
            if last is None or now - last > timeout:
                events.append(self._fault("sensor_lost", topic, f"{topic} 超时无数据"))
                continue
            span = max(0.0, last - (stat.get("first_ts") or now))
            freq = stat["count"] / span if span > 0 else 0.0
            if freq < low_hz and span >= low_duration:
                events.append(self._fault("sensor_degraded", topic, f"{topic} 频率 {freq:.2f}Hz < {low_hz}Hz"))

        cpu = self.system_metrics.get("cpu", 0.0)
        temp = self.system_metrics.get("temp", 0.0)
        voltage = self.system_metrics.get("voltage", 0.0)
        if cpu > float(rules.get("cpu_high_pct", 85.0)):
            events.append(self._fault("resource_warning", "cpu", f"CPU {cpu:.1f}% 过高"))
        if temp > float(rules.get("temp_high_c", 85.0)):
            events.append(self._fault("resource_warning", "temp", f"温度 {temp:.1f}C 过高"))
        if 0 < voltage < float(rules.get("voltage_low_v", 10.5)):
            events.append(self._fault("resource_warning", "voltage", f"电压 {voltage:.2f}V 过低"))
        return events

    def _fault(self, ftype: str, source: str, reason: str) -> dict[str, Any]:
        key = f"{ftype}:{source}"
        fault = self.faults.get(key)
        now = self.clock()
        if fault is None:
            fault = {
                "type": ftype,
                "source": source,
                "reason": reason,
                "started": now,
                "duration_s": 0.0,
                "recovered": False,
            }
            self.faults[key] = fault
            self._emit_fault(fault)
        fault["duration_s"] = round(now - fault["started"], 3)
        return fault

    def _emit_fault(self, fault: dict[str, Any]) -> None:
        payload = dict(fault)
        payload["event"] = "fault_start"
        self.publish("/dashboard/faults", payload)
        if self.on_fault:
            self.on_fault(payload)

    def clear_recovered_faults(self) -> None:
        now = self.clock()
        for key, fault in list(self.faults.items()):
            if fault["recovered"]:
                continue
            source = fault["source"]
            if fault["type"] == "resource_warning":
                recovered = not self._still_over_threshold(fault)
            else:
                # 话题故障在重新收到消息后恢复，而不是简单按时间自动消除。
                stat = self.topic_stats.get(source)
                recovered = bool(stat and stat.get("last_ts", 0) > fault["started"])
            if recovered:
                fault["recovered"] = True
                fault["duration_s"] = round(now - fault["started"], 3)
                payload = dict(fault)
                payload["event"] = "fault_recovered"
                self.publish("/dashboard/faults", payload)

    def _still_over_threshold(self, fault: dict[str, Any]) -> bool:
        rules = self.fault_rules
        source = fault["source"]
        if source == "cpu":
            return self.system_metrics.get("cpu", 0.0) > float(rules.get("cpu_high_pct", 85.0))
        if source == "temp":
            return self.system_metrics.get("temp", 0.0) > float(rules.get("temp_high_c", 85.0))
        if source == "voltage":
            v = self.system_metrics.get("voltage", 0.0)
            return 0 < v < float(rules.get("voltage_low_v", 10.5))
        return False

    def start(self) -> None:
        self._stop.clear()
        interval = 1.0 / self.metrics_hz if self.metrics_hz > 0 else 0.1
        while not self._stop.is_set():
            self.publish("/dashboard/metrics", self.collect_metrics())
            events = self.evaluate_faults()
            for _ in events:
                pass
            self.clear_recovered_faults()
            self._stop.wait(interval)

    def stop(self) -> None:
        self._stop.set()
