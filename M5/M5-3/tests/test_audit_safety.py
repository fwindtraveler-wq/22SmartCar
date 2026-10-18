# -*- coding: utf-8 -*-
"""审计链与分层急停的单测。"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "host_side"))
from audit import AuditLog, verify_file  # noqa: E402
from safety import SafetyController  # noqa: E402


def test_audit_chain_and_tamper_detection(tmp_path):
    log = AuditLog(tmp_path / "audit.jsonl")
    log.append("START", result="ok")
    log.append("MODEL_SWITCH", from_value="a", to_value="b", result="ok")
    ok, reason = verify_file(log.path, log.meta_path)
    assert ok, reason
    lines = log.path.read_text(encoding="utf-8").splitlines()
    lines[0] = lines[0].replace("START", "STOP")
    log.path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    ok, _ = verify_file(log.path, log.meta_path)
    assert not ok


def test_safety_layers_and_manual_reset(tmp_path):
    events = []
    audit_events = []
    safety = SafetyController(
        tmp_path / "blackbox.json",
        audit=lambda op, **fields: audit_events.append((op, fields)),
        publish=lambda t, p: events.append((t, p)),
        controller_estop=lambda: events.append(("controller_estop", {})),
    )
    safety.emergency_stop("test")
    assert safety.is_stopped()
    assert any(t == "/cmd_vel" for t, _ in events)
    assert any(t == "/emergency_stop" for t, _ in events)
    assert safety.reset(confirm=False)["ok"] is False
    assert safety.reset(confirm=True)["ok"] is True
