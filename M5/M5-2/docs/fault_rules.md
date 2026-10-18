# 故障判定规则

所有规则都在小车端 `DashboardAggregator.evaluate_faults()` 内执行，主机端
只负责显示，不根据图表重新判断。

| 故障 | 判定条件 | 解除条件 |
| :-- | :-- | :-- |
| `sensor_lost` | 某话题超过 `topic_timeout_s` 没有新消息 | 重新收到消息 |
| `sensor_degraded` | 某话题频率低于 `freq_low.threshold_hz` | 频率恢复到阈值以上 |
| `resource_warning` | CPU/温度/电压超过对应阈值 | 指标回落到阈值以内 |

阈值与持续时间见 `config/dashboard.yaml`。故障以 `/dashboard/faults` 事件发布，
包含 `type`、`source`、`reason`、`started`、`duration_s`、`recovered`。
