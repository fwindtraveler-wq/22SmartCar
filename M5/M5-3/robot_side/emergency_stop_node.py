#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""小车侧唯一新增订阅者：/emergency_stop 锁存急停。

收到急停后立即下发零速度，并把底盘置为急停锁存，直到收到人工复位，
防止控制器超时或其它指令源让车辆再次运动。
"""

from __future__ import annotations

import argparse
import json
from typing import Any, Callable


class EmergencyStopLatch:
    """与 ROS 无关的锁存逻辑，可单测。"""

    def __init__(self, publish: Callable[[str, Any], None]) -> None:
        self.publish = publish
        self.latched = False
        self.reason = ""

    def handle(self, message: Any) -> None:
        data = json.loads(message) if isinstance(message, str) else message
        if data.get("active"):
            self.latched = True
            self.reason = str(data.get("reason", "emergency_stop"))
            self.publish("/cmd_vel", {"linear": 0.0, "angular": 0.0})
            self.publish("/controller_estop", {"active": True, "reason": self.reason})
        elif data.get("active") is False:
            self.latched = False
            self.reason = ""


def main() -> None:
    parser = argparse.ArgumentParser(description="emergency stop subscriber")
    parser.add_argument("--sim", action="store_true")
    args = parser.parse_args()
    latch = EmergencyStopLatch(lambda t, m: print(t, m))
    if args.sim:
        latch.handle({"active": True, "reason": "test"})
        print({"latched": latch.latched, "reason": latch.reason})
        return
    try:
        import rclpy  # type: ignore
        from rclpy.node import Node  # type: ignore
        from std_msgs.msg import String  # type: ignore

        rclpy.init()
        node = Node("emergency_stop_subscriber")
        pub = node.create_publisher(String, "/cmd_vel", 10)

        def publish(topic, message):
            msg = String()
            msg.data = json.dumps(message, ensure_ascii=False)
            pub.publish(msg)

        latch = EmergencyStopLatch(publish)
        node.create_subscription(String, "/emergency_stop", lambda m: latch.handle(m.data), 10)
        rclpy.spin(node)
    except ImportError:
        raise SystemExit("未安装 rclpy；请使用 --sim 演示。")


if __name__ == "__main__":
    main()
