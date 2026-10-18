# M5-2 上位机可视化监控面板

## 运行

小车侧 ROS2：

```bash
ros2 run <pkg> dashboard_aggregator --ros-args -p topic_patterns:="[/perception/**,/navigation/**,/control/**,/hw/**]"
```

没有 ROS2 时可查看纯 Python 聚合核心：

```bash
python robot_side/dashboard_aggregator.py --sim
```

主机侧 Web：

```bash
python host_side/app.py --port 8080
```

启动后会自动打开浏览器；手机/平板可直接访问主机 IP 的 8080 端口。

## 演示

```bash
python host_side/app.py --demo
```

## 文件

- `robot_side/aggregator_core.py`：聚合与故障判定核心。
- `robot_side/dashboard_aggregator.py`：ROS2 Node 入口。
- `host_side/app.py`：零依赖 Web 服务。
- `config/dashboard.yaml`：话题模式与故障阈值。
- `docs/architecture.md`：双轨通信与取舍。
- `docs/fault_rules.md`：故障规则。
