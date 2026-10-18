# -*- coding: utf-8 -*-
"""节点注册表，负责把 YAML 中的 type 映射到具体 TaskNode 子类。"""

from __future__ import annotations

from typing import Dict, Type

from .nodes import (
    DetectTarget,
    ExecuteGrasp,
    NavigateTo,
    SpeakTTS,
    TaskNode,
    WaitForTrigger,
)


class Registry:
    """可扩展的节点类型注册表。

    外部新增节点时调用 register 即可，无需修改调度核心。
    """

    def __init__(self) -> None:
        self._types: Dict[str, Type[TaskNode]] = {
            "WaitForTrigger": WaitForTrigger,
            "NavigateTo": NavigateTo,
            "DetectTarget": DetectTarget,
            "ExecuteGrasp": ExecuteGrasp,
            "SpeakTTS": SpeakTTS,
        }

    def register(self, type_name: str, node_cls: Type[TaskNode]) -> None:
        self._types[type_name] = node_cls

    def available_types(self) -> list[str]:
        return sorted(self._types.keys())

    def validate_type(self, type_name: str) -> None:
        if type_name not in self._types:
            available = ", ".join(self.available_types())
            raise ValueError(f"未知节点类型 {type_name!r}，可用类型: {available}")

    def create(self, name: str, params: dict, ctx) -> TaskNode:
        type_name = params.get("type")
        self.validate_type(type_name)
        return self._types[type_name](name=name, params=params, ctx=ctx)
