#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成可异机验证的基线包：锁定参数、模型和自检脚本。"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import tarfile
import tempfile
import time
from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from yamlmini import dump_yaml, load_yaml  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
EXPERIMENTS = ROOT / "config" / "experiments"


def _resolve_config(args: argparse.Namespace) -> tuple[dict, str]:
    if args.exp:
        exp_meta = json.loads((EXPERIMENTS / f"{args.exp}.json").read_text(encoding="utf-8"))
        base = load_yaml(ROOT / exp_meta["base"]) if (ROOT / exp_meta["base"]).exists() else {}
        diff = load_yaml(EXPERIMENTS / f"{args.exp}.yaml") or {}
        merged = {**base, **diff}
        return merged, exp_meta["base"]
    scene = ROOT / args.scene
    return load_yaml(scene), str(scene.relative_to(ROOT))


def _verify_script(model_hashes: dict[str, str]) -> str:
    hashes = json.dumps(model_hashes, ensure_ascii=False)
    return f"""#!/usr/bin/env bash
set -euo pipefail

BASE_DIR="$(cd "$(dirname "${{BASH_SOURCE[0]}}")" && pwd)"
PYTHON="${{PYTHON:-python3}}"
FAIL=0

echo "[1/4] 检查 baseline.yaml"
if [[ ! -f "$BASE_DIR/baseline.yaml" ]]; then echo "FAIL: baseline.yaml 不存在"; exit 1; fi
"$PYTHON" -c "import sys, json, yaml" 2>/dev/null || "$PYTHON" -c "import sys, json; print('未安装 PyYAML，跳过结构解析')"

echo "[2/4] 检查 Python 版本"
"$PYTHON" - <<'PY'
import sys
if sys.version_info < (3, 9):
    raise SystemExit("需要 Python 3.9+")
print("PASS: Python", sys.version.split()[0])
PY

echo "[3/4] 检查模型哈希"
EXPECTED_HASHES='{hashes}'
if [[ -s "$BASE_DIR/baseline.sha256" ]]; then
  while read -r expected file; do
    if [[ ! -f "$BASE_DIR/models/$file" ]]; then
      echo "FAIL: 缺少模型文件 $file"
      FAIL=1
      continue
    fi
    actual=$(sha256sum "$BASE_DIR/models/$file" | awk '{{print $1}}')
    if [[ "$actual" != "$expected" ]]; then
      echo "FAIL: $file 哈希不一致"
      FAIL=1
    else
      echo "PASS: $file"
    fi
  done < "$BASE_DIR/baseline.sha256"
else
  echo "INFO: 无模型文件"
fi

echo "[4/4] 检查关键参数阈值"
"$PYTHON" - <<'PY'
import json
try:
    import yaml
    data = yaml.safe_load(open("baseline.yaml", encoding="utf-8"))
except Exception:
    import json
    # 使用标准库时 baseline.yaml 由本工具生成，可按 JSON 读取失败则跳过。
    data = json.load(open("baseline.yaml", encoding="utf-8"))
checks = {"nav_speed": (0.1, 3.0), "perception_hz": (1, 60), "min_confidence": (0.0, 1.0)}
for key, (lo, hi) in checks.items():
    if key in data and not (lo <= float(data[key]) <= hi):
        raise SystemExit(f"FAIL: {key} 超出阈值")
print("PASS: 关键参数阈值")
PY

if [[ $FAIL -ne 0 ]]; then echo "VERIFY FAIL"; exit 1; fi
echo "VERIFY PASS"
"""


def _package_readme(scene: str) -> str:
    return f"""# 基线包

- 来源场景: {scene}
- 生成时间: {time.strftime('%Y-%m-%d %H:%M:%S')}

## 使用

```bash
tar -xzf baseline_package_*.tar.gz
cd baseline_package_*
./verify_baseline.sh
```

验证脚本会检查 Python 版本、模型 SHA-256 和关键参数阈值，输出 `VERIFY PASS`。
"""


def main() -> int:
    parser = argparse.ArgumentParser(description="generate baseline package")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--exp", help="实验名")
    group.add_argument("--scene", help="场景文件路径")
    parser.add_argument("--out", required=True)
    parser.add_argument("--model-dir", default=None)
    args = parser.parse_args()

    config, scene = _resolve_config(args)
    out = ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        dump_yaml(config, tmp_path / "baseline.yaml")
        models_src = Path(args.model_dir) if args.model_dir else ROOT / "config" / "models"
        model_hashes: dict[str, str] = {}
        if models_src.exists():
            (tmp_path / "models").mkdir()
            for file in models_src.iterdir():
                if file.is_file() and not file.name.startswith("."):
                    shutil.copy2(file, tmp_path / "models" / file.name)
                    model_hashes[file.name] = hashlib.sha256(file.read_bytes()).hexdigest()
        if model_hashes:
            (tmp_path / "baseline.sha256").write_text(
                "\n".join(f"{h}  {name}" for name, h in model_hashes.items()) + "\n",
                encoding="utf-8",
            )
        (tmp_path / "verify_baseline.sh").write_text(_verify_script(model_hashes), encoding="utf-8")
        (tmp_path / "verify_baseline.sh").chmod(0o755)
        (tmp_path / "README.md").write_text(_package_readme(scene), encoding="utf-8")
        with tarfile.open(out, "w:gz") as tar:
            tar.add(tmp_path, arcname=out.stem.replace(".tar", ""))
    print(f"基线包已生成: {out} ({out.stat().st_size / 1024:.1f} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
