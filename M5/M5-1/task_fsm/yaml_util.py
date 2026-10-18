# -*- coding: utf-8 -*-
"""YAML 加载工具。

优先使用 PyYAML；在干净环境中缺失 PyYAML 时，回退到仅支持本任务 DSL 所需
子集的最小解析器。这样现场只依赖 Python 标准库也能运行。
"""

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
        parser = _MiniYamlParser(text)
        return parser.parse()


class YamlParseError(ValueError):
    """带行号和上下文信息的 YAML 解析错误，便于直接定位配置问题。"""

    def __init__(self, line_no: int, message: str) -> None:
        self.line_no = line_no
        super().__init__(f"YAML 第 {line_no} 行解析失败: {message}")


def _strip_comment(line: str) -> str:
    """去除引号外的注释，避免把字符串里的 # 误删。"""
    in_single = False
    in_double = False
    for i, ch in enumerate(line):
        if ch == "'" and not in_double:
            in_single = not in_single
        elif ch == '"' and not in_single:
            in_double = not in_double
        elif ch == "#" and not in_single and not in_double:
            return line[:i]
    return line


def _parse_scalar(raw: str) -> Any:
    value = raw.strip()
    if value == "":
        return None
    if value.startswith("[") and value.endswith("]"):
        return _parse_inline_list(value[1:-1])
    if value.startswith("{") and value.endswith("}"):
        return _parse_inline_dict(value[1:-1])
    if value in ("null", "~"):
        return None
    if value.lower() in ("true", "yes", "on"):
        return True
    if value.lower() in ("false", "no", "off"):
        return False
    if (value.startswith('"') and value.endswith('"')) or (
        value.startswith("'") and value.endswith("'")
    ):
        return value[1:-1]
    try:
        if value.isdigit():
            return int(value)
        return float(value)
    except ValueError:
        return value


def _split_top_level(text: str, sep: str = ",") -> list[str]:
    """按逗号切分，忽略引号与嵌套括号内的逗号。"""
    parts: list[str] = []
    start = 0
    depth = 0
    in_single = False
    in_double = False
    for i, ch in enumerate(text):
        if ch == "'" and not in_double:
            in_single = not in_single
        elif ch == '"' and not in_single:
            in_double = not in_double
        elif ch in "[{(" and not in_single and not in_double:
            depth += 1
        elif ch in "]})" and not in_single and not in_double:
            depth -= 1
        elif ch == sep and depth == 0 and not in_single and not in_double:
            parts.append(text[start:i].strip())
            start = i + 1
    parts.append(text[start:].strip())
    return [p for p in parts if p]


def _parse_inline_dict(text: str) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for item in _split_top_level(text, ","):
        if ":" not in item:
            continue
        key, _, raw_value = item.partition(":")
        result[key.strip().strip('"').strip("'")] = _parse_scalar(raw_value)
    return result


def _parse_inline_list(text: str) -> list[Any]:
    return [_parse_scalar(item) for item in _split_top_level(text, ",")]


class _MiniYamlParser:
    """仅解析本任务 DSL 所需的简单 YAML 结构。"""

    def __init__(self, text: str) -> None:
        self.lines = [
            _strip_comment(ln).rstrip()
            for ln in text.splitlines()
            if _strip_comment(ln).strip()
        ]

    def parse(self) -> Any:
        if not self.lines:
            return {}
        value, _ = self._parse_node(0, 0)
        return value

    def _indent(self, line: str) -> int:
        return len(line) - len(line.lstrip(" "))

    def _parse_node(self, index: int, indent: int) -> tuple[Any, int]:
        line = self.lines[index]
        if line[indent:].startswith("- "):
            return self._parse_sequence(index, indent)
        return self._parse_mapping(index, indent)

    def _parse_sequence(self, index: int, indent: int) -> tuple[list[Any], int]:
        values: list[Any] = []
        i = index
        while i < len(self.lines):
            line = self.lines[i]
            if self._indent(line) < indent:
                break
            if self._indent(line) != indent or not line[indent:].startswith("- "):
                break

            rest = line[indent + 2 :].strip()
            if rest == "":
                value, i = self._parse_node(i + 1, indent + 2)
                values.append(value)
                continue
            if ":" in rest:
                key, _, raw_value = rest.partition(":")
                item: dict[str, Any] = {}
                if raw_value.strip():
                    item[key.strip().strip('"').strip("'")] = _parse_scalar(raw_value)
                    i += 1
                else:
                    item[key.strip().strip('"').strip("'")] = None
                    i += 1
                    # 继续读取当前列表项的后续同缩进字段。
                    i = self._consume_map_fields(i, indent + 2, item)
                values.append(item)
                continue
            values.append(_parse_scalar(rest))
            i += 1
        return values, i

    def _parse_mapping(self, index: int, indent: int) -> tuple[dict[str, Any], int]:
        mapping: dict[str, Any] = {}
        i = index
        while i < len(self.lines):
            line = self.lines[i]
            if self._indent(line) < indent:
                break
            if self._indent(line) > indent:
                raise YamlParseError(i + 1, f"缩进异常: {line.strip()}")
            stripped = line[indent:]
            if stripped.startswith("- "):
                break
            if ":" not in stripped:
                raise YamlParseError(i + 1, f"缺少冒号: {stripped}")
            key, _, raw_value = stripped.partition(":")
            key = key.strip().strip('"').strip("'")
            if raw_value.strip():
                mapping[key] = _parse_scalar(raw_value)
                i += 1
            else:
                if i + 1 >= len(self.lines) or self._indent(self.lines[i + 1]) <= indent:
                    mapping[key] = None
                    i += 1
                else:
                    mapping[key], i = self._parse_node(i + 1, indent + 2)
        return mapping, i

    def _consume_map_fields(self, index: int, indent: int, mapping: dict[str, Any]) -> int:
        """读取列表对象中后续的 key: value 字段。"""
        i = index
        while i < len(self.lines):
            line = self.lines[i]
            if self._indent(line) < indent:
                break
            if self._indent(line) != indent or line[indent:].startswith("- "):
                break
            stripped = line[indent:]
            if ":" not in stripped:
                raise YamlParseError(i + 1, f"缺少冒号: {stripped}")
            key, _, raw_value = stripped.partition(":")
            key = key.strip().strip('"').strip("'")
            if raw_value.strip():
                mapping[key] = _parse_scalar(raw_value)
                i += 1
            else:
                if i + 1 >= len(self.lines) or self._indent(self.lines[i + 1]) <= indent:
                    mapping[key] = None
                    i += 1
                else:
                    mapping[key], i = self._parse_node(i + 1, indent + 2)
        return i
