# M5-3 裁判/交互/远程干预一体化终端

## 运行

裁判模拟器：

```bash
python tools/referee_sim.py
```

操作终端（浏览器自动打开，端口 8081）：

```bash
python host_side/operator_terminal.py --port 8081
```

审计校验：

```bash
python tools/verify_audit.py --log runtime/audit_log_20261003.jsonl
```

## 关键文件

- `host_side/referee_bridge.py`：裁判协议适配器。
- `host_side/operator_terminal.py`：一体化 Web 终端。
- `host_side/hot_switch.py`：参数/场景/模型热切换。
- `host_side/safety.py`：分层急停。
- `host_side/audit.py`：哈希链审计。
- `robot_side/emergency_stop_node.py`：小车侧唯一新增急停订阅者。
