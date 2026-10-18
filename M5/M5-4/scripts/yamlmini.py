# -*- coding: utf-8 -*-
"""M5-4 的极简 YAML 读写器，标准库实现。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_yaml(path: str | Path) -> Any:
    text = Path(path).read_text(encoding="utf-8")
    try:
        import yaml  # type: ignore

        return yaml.safe_load(text)
    except ImportError:
        return _Parser(text).parse()


def dump_yaml(data: Any, path: str | Path) -> None:
    text = _dump(data, 0)
    Path(path).write_text(text, encoding="utf-8")


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


def _dump(data: Any, indent: int) -> str:
    pad = "  " * indent
    if isinstance(data, dict):
        lines = []
        for key, value in data.items():
            if isinstance(value, (dict, list)):
                lines.append(f"{pad}{key}:")
                lines.append(_dump(value, indent + 1))
            else:
                lines.append(f"{pad}{key}: {_scalar_dump(value)}")
        return "\n".join(lines)
    if isinstance(data, list):
        lines = []
        for item in data:
            if isinstance(item, dict):
                first = next(iter(item), None)
                if first is not None and not isinstance(item[first], (dict, list)):
                    lines.append(f"{pad}- {first}: {_scalar_dump(item[first])}")
                    for key, value in list(item.items())[1:]:
                        if isinstance(value, (dict, list)):
                            lines.append(f"{'  '*(indent+1)}{key}:")
                            lines.append(_dump(value, indent + 2))
                        else:
                            lines.append(f"{'  '*(indent+1)}{key}: {_scalar_dump(value)}")
                else:
                    lines.append(f"{pad}-")
                    lines.append(_dump(item, indent + 1))
            else:
                lines.append(f"{pad}- {_scalar_dump(item)}")
        return "\n".join(lines)
    return f"{pad}{_scalar_dump(data)}"


def _scalar_dump(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False)
