#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""小车侧聚合节点：只运行一个 ROS2 Node，负责订阅、聚合、降频、判障。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from aggregator_core import DashboardAggregator


def load_config(path: str) -> dict:
    text = Path(path).read_text(encoding="utf-8")
    try:
        import yaml  # type: ignore

        return yaml.safe_load(text) or {}
    except ImportError:
        # 回退到同仓库中的极简 YAML 解析器，保证不依赖 PyYAML。
        import sys

        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "host_side"))
        from yamlmini import load

        return load(path) or {}


def _ros2_main(config: dict) -> None:
    import rclpy  # type: ignore
    from rclpy.node import Node  # type: ignore
    from rclpy.qos import QoSProfile  # type: ignore

    rclpy.init()
    node = Node("dashboard_aggregator")

    def publish(topic: str, payload) -> None:
        # 用标准 String 消息发布 JSON，避免自定义消息定义带来的部署成本。
        from std_msgs.msg import String  # type: ignore

        msg = String()
        msg.data = json.dumps(payload, ensure_ascii=False)
        pub = node.create_publisher(String, topic, QoSProfile(depth=10))
        pub.publish(msg)

    agg = DashboardAggregator(config, publish=publish)

    def callback(topic: str, message, stamp=None):
        agg.handle_message(topic, message, stamp)

    # 零硬编码：启动和运行时都枚举话题，节点晚启动也能自动接入。
    patterns = config.get("topic_patterns", [])
    seen: set[str] = set()

    def refresh():
        from std_msgs.msg import String  # type: ignore

        for topic, types in node.get_topic_names_and_types():
            if topic not in seen and any(_matches(p, topic) for p in patterns):
                seen.add(topic)
                node.create_subscription(String, topic, lambda msg, t=topic: callback(t, _decode(msg.data)), 10)

    node.create_timer(1.0, refresh)

    import threading

    threading.Thread(target=agg.start, daemon=True).start()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        agg.stop()
        node.destroy_node()
        rclpy.shutdown()


def _matches(pattern: str, topic: str) -> bool:
    return __import__("fnmatch").fnmatchcase(topic, pattern.replace("**", "*"))


def _decode(text: str):
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


def main() -> None:
    parser = argparse.ArgumentParser(description="M5-2 dashboard aggregator")
    parser.add_argument("--config", default="config/dashboard.yaml")
    parser.add_argument("--sim", action="store_true", help="使用本地模拟总线演示")
    args = parser.parse_args()
    config = load_config(args.config)

    if args.sim:
        from sim_bus import SimBus

        bus = SimBus()
        agg = DashboardAggregator(config, publish=bus.publish)
        # 模拟几个原始话题，证明零配置订阅与故障检测可以脱离 ROS 运行。
        bus.subscribe("/dashboard/**", lambda t, m, s: None)
        bus.publish("/perception/camera", {"expected_hz": 20, "latency_ms": 2.0})
        agg.handle_message("/perception/camera", {"expected_hz": 20, "latency_ms": 2.0})
        print(json.dumps(agg.collect_metrics(), ensure_ascii=False))
        return

    try:
        _ros2_main(config)
    except ImportError:
        raise SystemExit("未安装 rclpy；请使用 --sim 演示纯 Python 聚合核心。")


if __name__ == "__main__":
    main()
