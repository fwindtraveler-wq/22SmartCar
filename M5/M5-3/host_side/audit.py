# -*- coding: utf-8 -*-
"""只追加的哈希链审计日志。"""

from __future__ import annotations

import hashlib
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any

GENESIS = "0" * 64


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="milliseconds")


def _digest(entry: dict[str, Any]) -> str:
    canonical = json.dumps(entry, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class AuditLog:
    """追加审计记录，并生成前一行的哈希。"""

    def __init__(self, path: str | Path, user: str = "operator") -> None:
        self.path = Path(path)
        self.user = user
        self.meta_path = self.path.with_suffix(self.path.suffix + ".meta.json")
        self._count = 0
        self._last_hash = GENESIS
        self._load_meta()

    def _load_meta(self) -> None:
        if self.meta_path.exists():
            meta = json.loads(self.meta_path.read_text(encoding="utf-8"))
            self._count = int(meta.get("count", 0))
            self._last_hash = str(meta.get("last_hash", GENESIS))

    def append(self, op: str, **fields: Any) -> dict[str, Any]:
        entry = {
            "ts": _now(),
            "op": op,
            "source": fields.pop("source", "ui"),
            "user": fields.pop("user", self.user),
            "result": fields.pop("result", "ok"),
            **fields,
            "prev_hash": self._last_hash,
        }
        entry["hash"] = _digest(entry)
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
        self._count += 1
        self._last_hash = entry["hash"]
        self._write_meta()
        return entry

    def _write_meta(self) -> None:
        self.meta_path.write_text(
            json.dumps({"count": self._count, "last_hash": self._last_hash}, indent=2),
            encoding="utf-8",
        )


def verify_file(path: str | Path, meta_path: str | Path | None = None) -> tuple[bool, str]:
    """校验整条哈希链；返回 (是否通过, 原因)。"""
    path = Path(path)
    meta_path = Path(meta_path) if meta_path else Path(str(path) + ".meta.json")
    if not path.exists():
        return False, f"日志不存在: {path}"

    prev = GENESIS
    count = 0
    last_hash = None
    with path.open("r", encoding="utf-8") as fh:
        for line_no, line in enumerate(fh, 1):
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError as exc:
                return False, f"第 {line_no} 行不是合法 JSON: {exc}"
            if entry.get("prev_hash") != prev:
                return False, f"第 {line_no} 行 prev_hash 不匹配"
            got = entry.get("hash")
            entry_without_hash = {k: v for k, v in entry.items() if k != "hash"}
            want = _digest(entry_without_hash)
            if got != want:
                return False, f"第 {line_no} 行内容被篡改"
            prev = got
            last_hash = got
            count += 1

    if meta_path.exists():
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        if meta.get("count", 0) != count:
            return False, "日志行数与元数据不一致（可能存在删除）"
        if meta.get("last_hash") != last_hash:
            return False, "最终哈希与元数据不一致（可能存在篡改）"
    return True, "PASS"
