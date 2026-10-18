# 任务 YAML 字段说明

评委只需按本文件书写测试 YAML，交给 `python run_task.py <yaml>` 即可运行。

## 顶层字段

| 字段 | 类型 | 必填 | 说明 |
| :-- | :-- | :-: | :-- |
| `task_id` | string | 否 | 任务编号，缺省自动生成 |
| `deadline` | number | 否 | 整个任务的截止秒数，超过后结果为 `TIMEOUT` |
| `retry_budget` | number | 否 | 全局重试总预算，防止无限重试 |
| `tasks` | list | 是 | 步骤列表，也支持别名 `steps` |

## 步骤通用字段

| 字段 | 类型 | 必填 | 说明 |
| :-- | :-- | :-: | :-- |
| `name` | string | 是 | 唯一名称，fallback 用此名称跳转 |
| `type` | string | 条件必填 | 五个标准类型之一；`parallel` 节点可省略 |
| `timeout` | number | 否 | 步骤超时秒数，默认 60 |
| `retry` | number | 否 | 失败后的重试次数，默认 0 |
| `retry_interval` | number | 否 | 重试间隔秒数，默认 1.0 |
| `fallback` | string | 否 | 失败并耗尽重试后跳转到的步骤名 |
| `on_fail` | string | 否 | `skip` 或 `abort`；缺省等同 `abort` |

## 节点专属字段

### WaitForTrigger

- `timeout`：等待触发或键盘空格的秒数。
- `keyboard`：是否启用空格触发，默认 `true`。

### NavigateTo

- `pose`：静态目标，例如 `{x: 2.0, y: 0.5, yaw: 0.0}`。
- `pose_from_context`：从上下文读取目标，例如 `target_pose`。

### DetectTarget

- `target_class`：目标类别，`*` 表示任意。
- `min_confidence`：最小置信度，默认 0.5。

### ExecuteGrasp

- `grasp_type`：抓取方式，默认 `top_down`。
- `grasp_pose`：可选抓取位姿；缺省使用上下文中的 `target_pose`。

### SpeakTTS

- `text`：要播放的文本。

## 并行分支

```yaml
- name: parallel_checks
  parallel:
    fail_policy: any_fail   # any_fail 或 all_must_succeed
    branches:
      - name: check_battery
        type: SpeakTTS
        text: 检查电量
      - name: check_lidar
        type: SpeakTTS
        text: 检查雷达
```

分支内任意一步 `FAILED` 都会导致并行节点失败；两种 `fail_policy` 在本框架中
都要求所有分支成功才算成功。

## 失败与降级语义

- 失败后先按 `retry` 重试，若仍失败且设置了 `fallback`，当前步骤记为 `SKIPPED`
  并跳转到目标步骤。
- 若没有 `fallback` 且 `on_fail: skip`，当前步骤记为 `SKIPPED`，任务继续。
- 若没有 `fallback` 且 `on_fail: abort`（缺省），任务记为 `FAILED` 并结束。

## 完整示例

见 `../tasks/task_demo.yaml`。
