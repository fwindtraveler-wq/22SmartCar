# M5-1 设计说明

## 1. 状态机

六个状态：`IDLE`、`RUNNING`、`SUCCESS`、`FAILED`、`SKIPPED`、`RETRYING`。

```text
IDLE --start--> RUNNING
RUNNING --ok--> SUCCESS --> 下一步
RUNNING --fail--> RETRYING --重试预算未耗尽--> RUNNING
RETRYING --预算耗尽--> fallback / SKIPPED / FAILED
RUNNING --timeout--> 按 fail 分支处理
```

调度器按 YAML 顺序执行，节点返回 `SUCCESS` 后进入下一步；失败后先在节点内部
按 `retry` 重试，再依据 `fallback` 或 `on_fail` 决定降级。

## 2. 关键取舍

- 重试预算：每步的 `retry` 控制该节点重试次数；任务级 `retry_budget` 是全局兜底。
  两种同时存在，先消耗全局预算，全局耗尽后即使本步还有次数也不再重试。
- fallback 指向的节点再次失败：跳转会被计入 `fallback_hops`，单节点访问次数也有限制。
  达到上限后任务直接 `FAILED`，不会无限回跳。
- 回跳：允许，例如 `navigate_to_grasp` 失败后回 `navigate_to_scan`；回跳有计数上限。
- cancel 语义：Python 不强杀线程，节点通过 `TaskContext.cancel_event` 协作退出。
  超时由调度器在线程外层 `join(timeout)` 判定，超时后调用节点 `cancel()` 并给 0.5s 收尾时间。
- 长任务进度：节点通过 `ctx.report_progress()` 上报百分比和文本，界面据此展示中间状态。

## 3. 目录结构

- `core.py`：调度内核，代码行数 < 200 行（不含节点实现）。
- `context.py`：任务级共享上下文。
- `nodes.py`：五个标准节点，均通过注入回调脱离 ROS2。
- `registry.py`：`type -> 节点类` 的注册表。
- `yaml_util.py`：YAML 加载，优先 PyYAML，缺失时使用标准库解析器。
