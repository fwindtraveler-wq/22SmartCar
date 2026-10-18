#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""一体化操作终端：Web UI + 裁判协议 + 热切换 + 安全 + 审计。"""

from __future__ import annotations

import argparse
import json
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from audit import AuditLog
from hot_switch import HotSwitch
from referee_bridge import RefereeBridge
from safety import SafetyController

ROOT = Path(__file__).resolve().parent


class Terminal:
    """集中保存裁判、安全、切换和审计的实时状态。"""

    def __init__(self, workdir: Path, user: str) -> None:
        self.user = user
        audit_path = workdir / f"audit_log_{time.strftime('%Y%m%d')}.jsonl"
        self.audit = AuditLog(audit_path, user=user)
        self.events: list[dict] = []

        def publish(topic: str, payload) -> None:
            # 无 ROS2 时只记录事件；真实部署可替换为 rosbridge 发布器。
            self.events.append({"ts": time.time(), "topic": topic, "payload": payload})

        self.safety = SafetyController(workdir / "blackbox.json", self.audit.append, publish)
        self.hot = HotSwitch(workdir / "switch_log.csv", self.audit.append)
        self.bridge = RefereeBridge(
            on_status=lambda s: self.events.append({"ts": time.time(), "topic": "/referee/status", "payload": s}),
            on_pause=lambda: self.safety.emergency_stop("referee_pause", source="referee"),
            on_resume=lambda: None,
        )

    def snapshot(self) -> dict:
        return {
            "referee": self.bridge.status(),
            "safety": {"stopped": self.safety.is_stopped(), "reason": getattr(self.safety, "_reason", "")},
            "events": list(self.events[-50:]),
            "user": self.user,
        }

    def command(self, action: str, args: dict) -> dict:
        if action == "start_task":
            self.bridge.parse({"cmd": "START", "countdown": args.get("countdown", 0), "stage": args.get("stage", "")})
            return {"ok": True}
        if action in ("pause", "resume", "stop"):
            self.bridge.parse({"cmd": action.upper()})
            return {"ok": True}
        if action == "penalty":
            self.bridge.parse({"cmd": "PENALTY", "penalty_time": args.get("penalty_time", 0)})
            return {"ok": True}
        if action == "skip_current":
            self.audit.append("SKIP_NODE", node=args.get("node", "unknown"), user=self.user, result="ok")
            return {"ok": True}
        if action == "emergency_stop":
            return self.safety.emergency_stop(args.get("reason", "manual_stop"), source="ui", user=self.user)
        if action == "reset":
            return self.safety.reset(user=self.user, confirm=bool(args.get("confirm", False)))
        if action == "help":
            self.audit.append("REFEREE_HELP", user=self.user, result="ok")
            return {"ok": True, "message": "已请求裁判介入"}
        if action == "switch_model":
            return self.hot.switch("model", args.get("target"), user=self.user)
        if action == "switch_scene":
            return self.hot.switch("scene", args.get("target"), user=self.user)
        if action == "set_param":
            return self.hot.set_param(args.get("name", ""), args.get("value"), user=self.user)
        if action == "hard_reset":
            return {"ok": False, "reason": "比赛中禁止硬复位，需二次确认"}
        return {"ok": False, "reason": f"未知动作 {action}"}


STATE: Terminal | None = None


class Handler(BaseHTTPRequestHandler):
    server_version = "M5OperatorTerminal/1.0"

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/":
            self._serve_file(ROOT / "templates" / "index.html", "text/html")
        elif path.startswith("/static/"):
            file = (ROOT / "static" / path[len("/static/") :]).resolve()
            if not str(file).startswith(str((ROOT / "static").resolve())):
                self._json({"error": "forbidden"}, 403)
                return
            ctype = "text/javascript" if file.suffix == ".js" else "text/css"
            self._serve_file(file, ctype)
        elif path == "/api/stream":
            self._stream()
        elif path == "/api/state":
            self._json(STATE.snapshot())
        else:
            self._json({"error": "not found"}, 404)

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        if path != "/api/command":
            self._json({"error": "not found"}, 404)
            return
        try:
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", "0"))) or b"{}")
            result = STATE.command(body.get("action", ""), body.get("args", {}))
            self._json(result)
        except Exception as exc:
            self._json({"ok": False, "reason": str(exc)}, 400)

    def _stream(self) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        try:
            while True:
                self.wfile.write(f"data: {json.dumps(STATE.snapshot(), ensure_ascii=False)}\n\n".encode())
                self.wfile.flush()
                time.sleep(0.3)
        except (BrokenPipeError, ConnectionResetError):
            return

    def _serve_file(self, path: Path, ctype: str) -> None:
        if not path.exists():
            self._json({"error": "not found"}, 404)
            return
        body = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", ctype + "; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _json(self, obj, status=200) -> None:
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        pass


def main() -> None:
    global STATE
    parser = argparse.ArgumentParser(description="M5-3 operator terminal")
    parser.add_argument("--port", type=int, default=8081)
    parser.add_argument("--workdir", default=str(ROOT.parent / "runtime"))
    parser.add_argument("--user", default="operator")
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    workdir = Path(args.workdir)
    workdir.mkdir(parents=True, exist_ok=True)
    STATE = Terminal(workdir, args.user)
    server = ThreadingHTTPServer(("0.0.0.0", args.port), Handler)
    if not args.no_browser:
        threading.Timer(0.6, lambda: webbrowser.open(f"http://127.0.0.1:{args.port}")).start()
    print(f"操作终端已启动: http://127.0.0.1:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()


if __name__ == "__main__":
    main()
