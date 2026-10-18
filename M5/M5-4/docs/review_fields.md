# 复盘字段定义

`quick_review.py` 输出的 Markdown 包含以下字段：

- `task_result`：`SUCCESS` / `FAILED` / `TIMEOUT`，来自 M5-1 的 `task_report.json`。
- `total_elapsed_s`：任务总耗时。
- `steps`：每个子任务的耗时、重试次数和是否降级。
- `metrics`：导航成功率、路径偏差、感知频率、置信度均值、CPU/温度/电压峰值。
- `root_causes`：因果链，格式为 `现象(证据) -> 动作 -> 代价`。
- `switches`：来自 M5-3 `switch_log.csv` 的参数/模型切换记录。

## 时间对齐

MCAP 使用仿真系统时钟（纳秒），任务报告使用墙钟时间；本工具按时间戳排序后
只做同一次运行内的相对分析，不把 MCAP 时间与日志墙钟时间强行做绝对对齐。
