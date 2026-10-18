# M5-1 任务状态机

纯 Python 实现，不依赖 BehaviorTree.CPP、Groot2、py_trees。核心调度器位于
`task_fsm/core.py`，总行数小于 200 行。

## 运行

```bash
python run_task.py tasks/task_demo.yaml
```

默认使用 Mock 服务回调，示例 YAML 可直接跑通；需要接入真实 ROS2 回调时加 `--live`。
成功退出码为 0，失败/超时/中止为非 0；同时生成 `task_report.json`。

## 单元测试

```bash
pytest tests/ -q
```

测试使用 Mock 服务回调和 Mock 主题快照，不依赖 ROS2 运行时。

## 文件说明

- `task_fsm/core.py`：调度内核。
- `task_fsm/context.py`：`TaskContext` 共享上下文。
- `task_fsm/nodes.py`：五个标准节点。
- `task_fsm/registry.py`：节点注册表。
- `task_fsm/logger.py`：彩色日志。
- `task_fsm/yaml_util.py`：YAML 加载，含标准库回退解析器。
- `docs/dsl.md`：YAML DSL 完整说明。
- `docs/design.md`：状态机与取舍说明。
