# M5-2 架构说明

## 双轨通信

- 低频控制/状态：`WebSocket`/SSE + JSON，可经 `rosbridge` 穿 NAT，频率 < 10Hz。
- 高频指标：`/dashboard/metrics` 走原生 DDS，10Hz，延迟低且带宽可控。
- 图像：比赛模式默认 `video.enable: false`，只走 `web_video_server` MJPEG 1~2Hz。

## 为什么小车端算频率和丢包

时间戳只在话题进入小车端时最准确；若把原始时间戳全部推到主机，主机不仅要
承担大量 JSON 解码，还会因传输抖动污染计算。因此聚合器直接维护每个话题的
首尾时间戳和计数，主机端只消费聚合结果。

## 为什么 metrics 固定 10Hz

人眼刷新率约 10Hz 就能感觉实时，继续提高对比赛信息没有收益，却会成倍增加
带宽。单个 JSON 指标约 1~3KB，10Hz 下约 10~30KB/s，远低于 DDS 常见承载能力。

## 零配置发现

ROS2 适配层使用 `get_topic_names_and_types()` 枚举当前话题，再按 YAML 中的
`topic_patterns` 动态订阅。节点晚启动时，面板会自动显示已有话题；尚未出现的
话题会保持“无数据”状态，待出现后再接入。

## 导出机制

`/api/export` 返回一个自包含 HTML，`window.__EXPORT_DATA__` 中嵌入全部历史
指标、故障与任务状态，可直接离线回放，不是截图。
