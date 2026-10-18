#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""上位机 Web 监控面板。

只依赖 Python 标准库：HTTP 服务 + Server-Sent Events。聚合器通过 POST /ingest
推送 JSON，浏览器通过 /api/stream 实时接收；没有数据时明确显示“失联”，
而不是把缺失数据画成 0。
"""

from __future__ import annotations

import argparse
import json
import threading
import time
import webbrowser
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from yamlmini import load as load_yaml


ROOT = Path(__file__).resolve().parent


class MetricStore:
    """保留最近 600 个聚合快照，供导出和回放使用。"""

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.history: deque[dict] = deque(maxlen=600)
        self.latest: dict = {}
        self.faults: list[dict] = []
        self.task_state: dict = {}

    def ingest(self, payload: dict) -> None:
        kind = payload.get("type", "metrics")
        data = payload.get("data") or payload
        ts = data.get("ts") or time.time()
        with self.lock:
            if kind == "metrics":
                self.latest = data
                self.history.append(data)
            elif kind == "fault":
                self.faults.append({"ts": ts, **data})
            elif kind == "task_state":
                self.task_state = data

    def snapshot(self) -> dict:
        with self.lock:
            return {
                "latest": self.latest,
                "faults": list(self.faults[-50:]),
                "task_state": self.task_state,
                "history": list(self.history),
            }


class Store:
    instance = MetricStore()


class DashboardHandler(BaseHTTPRequestHandler):
    """零配置静态文件 + JSON API + SSE。"""

    server_version = "M5Dashboard/1.0"

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/" or path == "/index.html":
            self._serve_file(ROOT / "templates" / "index.html", "text/html")
        elif path.startswith("/static/"):
            rel = path[len("/static/") :]
            file = (ROOT / "static" / rel).resolve()
            if not str(file).startswith(str((ROOT / "static").resolve())):
                self._json({"error": "forbidden"}, 403)
                return
            ctype = "text/javascript" if file.suffix == ".js" else "text/css"
            self._serve_file(file, ctype)
        elif path == "/api/stream":
            self._stream()
        elif path == "/api/snapshot":
            self._json(Store.instance.snapshot())
        elif path == "/api/export":
            self._export()
        elif path == "/favicon.ico":
            self._text("", 204)
        else:
            self._json({"error": "not found"}, 404)

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        if path == "/ingest":
            try:
                length = int(self.headers.get("Content-Length", "0"))
                payload = json.loads(self.rfile.read(length) or b"{}")
                Store.instance.ingest(payload)
                self._json({"ok": True})
            except Exception as exc:
                self._json({"ok": False, "error": str(exc)}, 400)
        elif path == "/api/command":
            try:
                length = int(self.headers.get("Content-Length", "0"))
                payload = json.loads(self.rfile.read(length) or b"{}")
                # 面板只负责把指令转发给一体化终端，紧急停车的分层逻辑由 M5-3 执行。
                self._json({"ok": True, "queued": payload.get("action", "unknown")})
            except Exception as exc:
                self._json({"ok": False, "error": str(exc)}, 400)
        else:
            self._json({"error": "not found"}, 404)

    def _serve_file(self, path: Path, ctype: str) -> None:
        if not path.exists():
            self._text("not found", 404)
            return
        body = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", ctype + "; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _stream(self) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.end_headers()
        try:
            while True:
                snapshot = Store.instance.snapshot()
                event = {
                    "ts": time.time(),
                    "latest": snapshot["latest"],
                    "faults": snapshot["faults"],
                    "task_state": snapshot["task_state"],
                }
                self.wfile.write(f"data: {json.dumps(event, ensure_ascii=False)}\n\n".encode())
                self.wfile.flush()
                time.sleep(0.2)
        except (BrokenPipeError, ConnectionResetError):
            return

    def _export(self) -> None:
        html = (ROOT / "templates" / "index.html").read_text(encoding="utf-8")
        data = json.dumps(Store.instance.snapshot(), ensure_ascii=False)
        html = html.replace(
            "<script id=\"export-data\" type=\"application/json\"></script>",
            f"<script id=\"export-data\" type=\"application/json\">{data}</script>",
        )
        self._serve_bytes(html.encode("utf-8"), "text/html")

    def _serve_bytes(self, body: bytes, ctype: str) -> None:
        self.send_response(200)
        self.send_header("Content-Type", ctype + "; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _json(self, obj: dict, status: int = 200) -> None:
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _text(self, text: str, status: int = 200) -> None:
        body = text.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if body:
            self.wfile.write(body)

    def log_message(self, fmt: str, *args) -> None:
        # 降低控制台噪音。
        pass


def _run_demo(config: dict, port: int) -> None:
    """在没有 ROS2 时启动一个聚合器，把指标 POST 给当前 Web 服务。"""
    from urllib.request import Request, urlopen

    import sys

    sys.path.insert(0, str(ROOT.parent / "robot_side"))
    from aggregator_core import DashboardAggregator

    def publish(topic: str, payload) -> None:
        try:
            data = json.dumps(payload, ensure_ascii=False).encode()
            urlopen(Request(f"http://127.0.0.1:{port}/ingest", data=data, headers={"Content-Type": "application/json"}))
        except Exception:
            pass

    agg = DashboardAggregator(config, publish=publish)
    # 模拟几个原始话题，方便演示面板布局与故障流。
    for topic, value in [
        ("/perception/camera", {"expected_hz": 20, "latency_ms": 3.0}),
        ("/navigation/status", {"expected_hz": 10, "latency_ms": 1.0}),
        ("/hw/temp", {"temperature": 42.0}),
        ("/hw/cpu", {"percent": 20.0}),
    ]:
        agg.handle_message(topic, value)
    agg.start()


def main() -> None:
    parser = argparse.ArgumentParser(description="M5-2 host dashboard")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--config", default=str(ROOT.parent / "config" / "dashboard.yaml"))
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--demo", action="store_true")
    args = parser.parse_args()

    config = load_yaml(args.config) if Path(args.config).exists() else {}
    server = ThreadingHTTPServer(("0.0.0.0", args.port), DashboardHandler)
    if not args.no_browser:
        threading.Timer(0.6, lambda: webbrowser.open(f"http://127.0.0.1:{args.port}")).start()
    if args.demo:
        threading.Thread(target=_run_demo, args=(config, args.port), daemon=True).start()
    print(f"面板已启动: http://127.0.0.1:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()


if __name__ == "__main__":
    main()
