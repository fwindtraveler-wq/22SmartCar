#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""审计哈希链校验工具。"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "host_side"))
from audit import verify_file  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="verify audit chain")
    parser.add_argument("--log", required=True)
    parser.add_argument("--meta", default=None)
    args = parser.parse_args()
    ok, reason = verify_file(args.log, args.meta)
    print(reason)
    raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    main()
