# 从跑完到 promote 的完整工作流

1. 跑完一把后执行：

   ```bash
   python scripts/quick_review.py --mcap data/run_01.mcap --logs data/logs --switch-log data/switch_log.csv
   ```

2. 创建实验并运行多把：

   ```bash
   python scripts/exp.py new --name nav_speed_0.9 --base config/scene_race.yaml --set nav_speed=0.9 --desc "直线速度测试"
   python scripts/exp.py run --name nav_speed_0.9 --runs 3
   ```

3. 对比并晋升基线：

   ```bash
   python scripts/exp.py compare --names nav_speed_0.9,nav_speed_1.0 --metric nav_time,success_rate,cpu_peak
   python scripts/exp.py promote --name nav_speed_0.9 --to config/scene_race.yaml
   ```

4. 生成异机验证包：

   ```bash
   python scripts/gen_baseline.py --exp nav_speed_0.9 --out outputs/baseline_package_20261003.tar.gz
   ```

解压后执行 `./verify_baseline.sh`，通过即输出 `VERIFY PASS`。
