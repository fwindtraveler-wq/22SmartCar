# M5-4 复盘与实验管理工具链

## 单次复盘

```bash
python scripts/quick_review.py --mcap data/run_01.mcap --logs data/logs --switch-log data/switch_log.csv
```

只解析 `config/key_topics.yaml` 中的关键话题，因此从启动到输出结论小于 30 秒。

## 实验流程

```bash
python scripts/exp.py new --name nav_speed_0.9 --base config/scene_race.yaml --set nav_speed=0.9
python scripts/exp.py run --name nav_speed_0.9 --runs 3
python scripts/exp.py compare --names nav_speed_0.9,nav_speed_1.0 --metric nav_time,success_rate
python scripts/exp.py promote --name nav_speed_0.9 --to config/scene_race.yaml
```

## 基线包

```bash
python scripts/gen_baseline.py --exp nav_speed_0.9 --out outputs/baseline_package_20261003.tar.gz
```

解压后执行 `./verify_baseline.sh`，脚本会检查模型哈希、Python 版本和关键参数阈值。
