# -*- coding: utf-8 -*-
"""极简 YAML 子集解析器，仅用于读取 dashboard.yaml。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load(path: str | Path) -> Any:
    text = Path(path).read_text(encoding="utf-8")
    try:
        import yaml  # type: ignore

        return yaml.safe_load(text)
    except ImportError:
        return _Parser(text).parse()


class _Parser:
    def __init__(self, text: str) -> None:
        self.lines = [ln.rstrip() for ln in text.splitlines() if ln.strip() and not ln.lstrip().startswith("#")]

    def parse(self) -> Any:
        value, _ = self._node(0, 0)
        return value

    def _indent(self, line: str) -> int:
        return len(line) - len(line.lstrip(" "))

    def _node(self, i: int, indent: int):
        line = self.lines[i]
        if line[indent:].startswith("- "):
            return self._seq(i, indent)
        return self._map(i, indent)

    def _seq(self, i: int, indent: int):
        values = []
        while i < len(self.lines):
            line = self.lines[i]
            if self._indent(line) < indent or self._indent(line) != indent or not line[indent:].startswith("- "):
                break
            rest = line[indent + 2 :].strip()
            if rest == "":
                val, i = self._node(i + 1, indent + 2)
                values.append(val)
            elif ":" in rest:
                key, _, raw = rest.partition(":")
                obj = {}
                if raw.strip():
                    obj[key.strip()] = _scalar(raw)
                    i += 1
                else:
                    obj[key.strip()] = None
                    i += 1
                    i = self._fields(i, indent + 2, obj)
                values.append(obj)
            else:
                values.append(_scalar(rest))
                i += 1
        return values, i

    def _map(self, i: int, indent: int):
        obj = {}
        while i < len(self.lines):
            line = self.lines[i]
            if self._indent(line) < indent:
                break
            if self._indent(line) > indent:
                raise ValueError(f"缩进异常第 {i+1} 行")
            if line[indent:].startswith("- "):
                break
            if ":" not in line[indent:]:
                raise ValueError(f"缺少冒号第 {i+1} 行")
            key, _, raw = line[indent:].partition(":")
            key = key.strip()
            if raw.strip():
                obj[key] = _scalar(raw)
                i += 1
            else:
                if i + 1 >= len(self.lines) or self._indent(self.lines[i + 1]) <= indent:
                    obj[key] = None
                    i += 1
                else:
                    obj[key], i = self._node(i + 1, indent + 2)
        return obj, i

    def _fields(self, i: int, indent: int, obj: dict):
        while i < len(self.lines):
            line = self.lines[i]
            if self._indent(line) < indent or self._indent(line) != indent or line[indent:].startswith("- "):
                break
            key, _, raw = line[indent:].partition(":")
            key = key.strip()
            if raw.strip():
                obj[key] = _scalar(raw)
                i += 1
            else:
                obj[key], i = self._node(i + 1, indent + 2)
        return i


def _scalar(raw: str) -> Any:
    value = raw.strip()
    if value.startswith("[") and value.endswith("]"):
        return json.loads(value)
    if value.startswith("{") and value.endswith("}"):
        return json.loads(value)
    if value in ("true", "false"):
        return value == "true"
    if value.isdigit():
        return int(value)
    try:
        return float(value)
    except ValueError:
        return value.strip('"').strip("'")
