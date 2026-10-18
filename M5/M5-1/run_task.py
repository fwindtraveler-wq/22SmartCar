#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""任务状态机命令行入口。

用法:
    python run_task.py tasks/task_demo.yaml

成功时退出码为 0，其余情况为非 0，方便 CI 和脚本判断。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from task_fsm.context import TaskContext
from task_fsm.core import TaskRunner
from task_fsm.logger import Logger
from task_fsm.yaml_util import YamlParseError, load_yaml


def build_mock_context() -> TaskContext:
    """构造脱离 ROS2 的 Mock 上下文，保证示例 YAML 可直接跑通。"""
    ctx = TaskContext()
    ctx.trigger_event.set()
    ctx.service_callbacks = {
        "navigate_to_pose": lambda payload: {"status": "SUCCESS"},
        "manipulation_grasp": lambda payload: {"status": "SUCCESS", "object_pose": payload.get("grasp_pose")},
        "tts_speak": lambda payload: {"status": "SUCCESS"},
    }
    ctx.topic_snapshot = {
        "perception_targets": lambda: [
            {"class": "qrcode", "confidence": 0.9, "id": "qr_01", "pose": [2.1, 0.4]}
        ]
    }
    return ctx


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="运行 M5-1 任务状态机")
    parser.add_argument("task_yaml", help="任务 YAML 文件路径")
    parser.add_argument("--report", default="task_report.json", help="输出报告路径")
    parser.add_argument("--no-color", action="store_true", help="关闭彩色日志")
    parser.add_argument("--live", action="store_true", help="使用真实 ROS2 回调（未注入时节点会失败）")
    args = parser.parse_args(argv)

    try:
        task = load_yaml(args.task_yaml)
        ctx = TaskContext() if args.live else build_mock_context()
        runner = TaskRunner(task, ctx=ctx, logger=Logger(color=not args.no_color))
        report = runner.run()
    except YamlParseError as exc:
        print(f"配置错误: {exc}", file=sys.stderr)
        return 2
    except (KeyError, ValueError) as exc:
        print(f"任务配置错误: {exc}", file=sys.stderr)
        return 2

    Path(args.report).write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"报告已写入: {args.report}")
    return 0 if report["result"] == "SUCCESS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
