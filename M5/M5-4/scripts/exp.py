#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""实验管理器：new / run / compare / promote 四个子命令。"""

from __future__ import annotations

import argparse
import json
import math
import random
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from yamlmini import dump_yaml, load_yaml  # noqa: E402

ROOT = SCRIPT_DIR.parent
EXPERIMENTS = ROOT / "config" / "experiments"
RUNS = ROOT / "outputs" / "runs"


def deep_merge(base: dict[str, Any], overrides: dict[str, Any]) -> dict[str, Any]:
    out = dict(base)
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = deep_merge(out[key], value)
        else:
            out[key] = value
    return out


def parse_set(items: list[str]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for item in items:
        key, _, raw = item.partition("=")
        value: Any = raw
        if raw.isdigit():
            value = int(raw)
        else:
            try:
                value = float(raw)
            except ValueError:
                value = raw
        result[key] = value
    return result


def _write_simulated_run(rundir: Path, config: dict[str, Any], name: str, run_no: int) -> None:
    """为无实车环境生成可复现的样本，演示完整实验闭环。"""
    random.seed(f"{name}-{run_no}")
    nav_speed = float(config.get("nav_speed", 1.0))
    success = nav_speed < 1.1 or run_no > 0
    lines = []
    for i in range(40):
        ts = 1000 + i * 0.05
        lines.append(json.dumps({"timestamp": ts, "topic": "/perception/camera", "value": {"confidence": 0.85 - i * 0.002}}))
    for i in range(8):
        ts = 1002 + i * 0.5
        lines.append(json.dumps({"timestamp": ts, "topic": "/navigation/result", "value": {"status": "SUCCESS" if success else "FAILED", "elapsed_s": 2.0 / nav_speed, "path_deviation": 0.2 * (nav_speed - 0.8)}}))
    lines.append(json.dumps({"timestamp": 1004, "topic": "/hw/temp", "value": {"temperature": 78.0 + (nav_speed - 0.8) * 20}}))
    lines.append(json.dumps({"timestamp": 1005, "topic": "/hw/cpu", "value": {"percent": 55.0 + (nav_speed - 0.8) * 30}}))
    (rundir / "run.mcap").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (rundir / "task_report.json").write_text(
        json.dumps(
            {
                "task_id": f"{name}_{run_no}",
                "result": "SUCCESS" if success else "FAILED",
                "total_elapsed_s": round(18.0 / nav_speed, 2),
                "steps": [
                    {"name": "nav", "status": "SUCCESS" if success else "FAILED", "elapsed_s": round(2.0 / nav_speed, 2), "retries": 0 if success else 1, "degraded": not success}
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (rundir / "logs").mkdir(exist_ok=True)
    (rundir / "logs" / "node.log").write_text("fallback triggered due to navigation timeout\n" if not success else "navigation ok\n", encoding="utf-8")
    (rundir / "switch_log.csv").write_text("ts,kind,from,to,user,result\n0,param,nav_speed,0.8,operator,ok\n", encoding="utf-8")


def run_review_for_run(rundir: Path, key_topics_path: Path) -> dict[str, Any]:
    import parse_mcap
    import quick_review

    key_topics = parse_mcap.load_key_topics(key_topics_path)
    review = quick_review.build_review(
        rundir / "run.mcap",
        rundir / "logs",
        rundir / "switch_log.csv",
        rundir / "task_report.json",
        key_topics,
    )
    (rundir / "summary.json").write_text(json.dumps(review, ensure_ascii=False, indent=2), encoding="utf-8")
    return review


def cmd_new(args: argparse.Namespace) -> int:
    EXPERIMENTS.mkdir(parents=True, exist_ok=True)
    base_path = ROOT / args.base
    base = load_yaml(base_path) if base_path.exists() else {}
    changes = parse_set(args.set)
    diff = deep_merge({}, changes)
    meta = {
        "name": args.name,
        "base": args.base,
        "desc": args.desc,
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "changes": changes,
    }
    dump_yaml(diff, EXPERIMENTS / f"{args.name}.yaml")
    (EXPERIMENTS / f"{args.name}.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"已创建实验 {args.name}，差异配置只记录 {list(changes)}")
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    exp_path = EXPERIMENTS / f"{args.name}.json"
    diff_path = EXPERIMENTS / f"{args.name}.yaml"
    if not exp_path.exists() or not diff_path.exists():
        print(f"实验 {args.name} 不存在", file=sys.stderr)
        return 1
    meta = json.loads(exp_path.read_text(encoding="utf-8"))
    base = load_yaml(ROOT / meta["base"]) if (ROOT / meta["base"]).exists() else {}
    diff = load_yaml(diff_path) or {}
    config = deep_merge(base, diff)
    rundir_root = RUNS / args.name
    summaries = []
    for i in range(args.runs):
        rundir = rundir_root / f"run_{i}"
        rundir.mkdir(parents=True, exist_ok=True)
        _write_simulated_run(rundir, config, args.name, i)
        summary = run_review_for_run(rundir, ROOT / "config" / "key_topics.yaml")
        summaries.append(summary)
    agg = {
        "name": args.name,
        "runs": args.runs,
        "metrics": {},
        "success_rate": round(sum(1 for s in summaries if s["task_result"] == "SUCCESS") / args.runs, 3),
    }
    metric_names = summaries[0]["metrics"].keys() if summaries else []
    for key in metric_names:
        values = [s["metrics"][key] for s in summaries if isinstance(s["metrics"].get(key), (int, float))]
        if values:
            agg["metrics"][key] = {
                "mean": round(sum(values) / len(values), 3),
                "std": round((sum((v - sum(values) / len(values)) ** 2 for v in values) / len(values)) ** 0.5, 3),
            }
    (rundir_root / "summary.json").write_text(json.dumps(agg, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"实验 {args.name} 已完成 {args.runs} 把，成功率 {agg['success_rate']}")
    return 0


def cmd_compare(args: argparse.Namespace) -> int:
    names = [n.strip() for n in args.names.split(",") if n.strip()]
    metrics = [m.strip() for m in args.metric.split(",") if m.strip()]
    data = []
    for name in names:
        summary = RUNS / name / "summary.json"
        if summary.exists():
            data.append((name, json.loads(summary.read_text(encoding="utf-8"))))
    md_lines = ["# 实验对比", "", "| 实验 | " + " | ".join(metrics) + " | 成功率 |", "| :-- | " + " | ".join(":--" for _ in metrics) + " | :-- |"]
    for name, summary in data:
        cells = [str(summary["metrics"].get(m, {}).get("mean", "-")) for m in metrics]
        md_lines.append(f"| {name} | " + " | ".join(cells) + f" | {summary.get('success_rate', '-')} |")
    (ROOT / "outputs").mkdir(exist_ok=True)
    out_md = ROOT / "outputs" / f"compare_{'_'.join(names)}.md"
    out_md.write_text("\n".join(md_lines) + "\n", encoding="utf-8")
    html = _comparison_html(names, metrics, data)
    out_html = out_md.with_suffix(".html")
    out_html.write_text(html, encoding="utf-8")
    print(f"对比已生成: {out_md} 和 {out_html}")
    return 0


def _comparison_html(names: list[str], metrics: list[str], data: list[tuple[str, dict]]) -> str:
    rows = json.dumps([{"name": n, "metrics": d.get("metrics", {}), "success": d.get("success_rate")} for n, d in data], ensure_ascii=False)
    return f"""<!doctype html><html><head><meta charset="utf-8"><title>实验对比</title></head>
<body><h1>实验对比</h1><div id="chart" style="height:320px"></div><script>
var rows={rows}; var metrics={json.dumps(metrics)};
var html='<table border=1><tr><th>实验</th>'+metrics.map(function(m){{return '<th>'+m+'</th>'}}).join('')+'<th>成功率</th></tr>';
rows.forEach(function(r){{html+='<tr><td>'+r.name+'</td>'+metrics.map(function(m){{var v=r.metrics[m]; return '<td>'+(v?v.mean:'-')+'</td>'}}).join('')+'<td>'+r.success+'</td></tr>'}});
document.getElementById('chart').innerHTML=html;
</script></body></html>"""


def cmd_promote(args: argparse.Namespace) -> int:
    exp_path = EXPERIMENTS / f"{args.name}.json"
    diff_path = EXPERIMENTS / f"{args.name}.yaml"
    if not exp_path.exists() or not diff_path.exists():
        print(f"实验 {args.name} 不存在", file=sys.stderr)
        return 1
    meta = json.loads(exp_path.read_text(encoding="utf-8"))
    target = ROOT / args.to
    base = load_yaml(target) if target.exists() else {}
    diff = load_yaml(diff_path) or {}
    merged = deep_merge(base, diff)
    dump_yaml(merged, target)
    # 只提交被 promote 修改的场景文件，不混入工作区中其它无关改动。
    repo = ROOT
    if (repo / ".git").exists():
        subprocess.run(["git", "-C", str(repo), "add", str(target.relative_to(repo))], check=False)
        subprocess.run(["git", "-C", str(repo), "commit", "-m", f"promote {args.name} to {args.to}"], check=False)
    else:
        print("当前目录不是 Git 仓库，跳过提交")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="experiment manager")
    sub = parser.add_subparsers(dest="command", required=True)
    p_new = sub.add_parser("new")
    p_new.add_argument("--name", required=True)
    p_new.add_argument("--base", required=True)
    p_new.add_argument("--set", nargs="+", default=[])
    p_new.add_argument("--desc", default="")
    p_run = sub.add_parser("run")
    p_run.add_argument("--name", required=True)
    p_run.add_argument("--runs", type=int, default=3)
    p_compare = sub.add_parser("compare")
    p_compare.add_argument("--names", required=True)
    p_compare.add_argument("--metric", required=True)
    p_promote = sub.add_parser("promote")
    p_promote.add_argument("--name", required=True)
    p_promote.add_argument("--to", required=True)
    args = parser.parse_args()
    if args.command == "new":
        return cmd_new(args)
    if args.command == "run":
        return cmd_run(args)
    if args.command == "compare":
        return cmd_compare(args)
    if args.command == "promote":
        return cmd_promote(args)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
