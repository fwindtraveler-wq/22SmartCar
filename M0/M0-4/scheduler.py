import argparse
import json
import os
import sys
import time
import random
from dataclasses import dataclass
import yaml
'''优化重构版本'''
#全局变量先定义
report = {"timeout": False, "total_duration": 0.0, "tasks": []}
report_json = ""

#颜色字典映射
statue_color_dict = {
    "SUCCESS": "\033[1;32m",   # 绿色
    "FAILED":  "\033[1;31m",   # 红色（任务失败 / 超时中断）
    "RETRY":   "\033[1;33m",   # 黄色
    "SKIPPED": "\033[1;34m",   # 蓝色
}
reset_color = "\033[0m"

#定义任务类，统一管理
@dataclass
class Task:
    name: str
    duration: float
    success_rate: float
    dependencies: list[str]
    success: int = 0    # 用 0 代表未执行，1 代表执行成功，2 代表执行失败
    status: str = ""    # 任务状态（4种）

#状态输出
def command_output(info):
    if info in statue_color_dict and sys.stdout.isatty():   #添加非TTY环境处理（防彩色乱码）
        print(statue_color_dict[info] + info + reset_color)
    else:
        print(info)

def error_process(info):
    command_output("FAILED")
    print(info, file=sys.stderr)
    sys.exit(1)

# 超时处理 定义超时异常类
class task_timeout_process(Exception):
    def __init__(self, key, attempts, started_at):
        super().__init__(key)#异常名称处理
        self.key = key
        self.attempts = attempts
        self.started_at = started_at

def timeout_test(realtime, timeout, key, attempts, started_at):
    if timeout is not None and realtime > timeout:
        raise task_timeout_process(key, attempts, started_at)

def success_calculate(task, started_at, start_time, timeout):
    attempts = 0
    while attempts < 3:
        timeout_test(time.time() - start_time, timeout, task.name, attempts, started_at)
        time.sleep(task.duration)
        attempts += 1
        timeout_test(time.time() - start_time, timeout, task.name, attempts, started_at)
        if random.random() < task.success_rate:
            return "SUCCESS", attempts
        print(task.name, end=" ")
        command_output("FAILED")
        if attempts < 3:
            print(task.name, end=" ")
            command_output("RETRY")
    return "FAILED", attempts

# 拓扑排序（新增）—— Kahn 算法--------------------------------------------------
def Kahn_sort(Tasks):
    depend_num = {name: len(t.dependencies) for name, t in Tasks.items()} #生成依赖项字典-正向
    children = {name: [] for name in Tasks}                               #依赖项解决后能做的任务-反向
    for name, t in Tasks.items():
        for dep in t.dependencies:
            children[dep].append(name)
    zero_dep_task = [name for name in Tasks if depend_num[name] == 0]
    order = []
    while zero_dep_task:
        name = zero_dep_task.pop(0)
        order.append(name)
        for child in children[name]:
            depend_num[child] -= 1
            if depend_num[child] == 0:
                zero_dep_task.append(child)
    if len(order) != len(Tasks):           #依赖成环检测
        error_process("检测到依赖环")
    return order

def read_request(config):
    try:
        with open(config, "r", encoding="utf-8") as f:
            ext = os.path.splitext(config)[1].lower()
            if ext == ".json":
                reader = json.load(f)
            elif ext == ".yaml" or ext == ".yml":
                reader = yaml.safe_load(f)
            else:
                error_process("配置文件后缀有误：仅支持 .yaml / .yml / .json")
        if not isinstance(reader, dict):
            error_process("配置文件错误,非字典类型")
        timeout = reader["timeout"]
        tasks = reader["tasks"]
        if not tasks:
            error_process("任务为空")
        Tasks = {}
        for item in tasks:
            if not isinstance(item, dict):
                error_process("任务配置必须是字典")
            name = item["name"]
            duration = item["duration"]
            rate = item["success_rate"]
            dependence = item["dependencies"]
            #错误处理
            if name in Tasks:
                error_process("存在重复的任务名：%s" % name)
            if not isinstance(duration, (int, float)) or duration < 0:
                error_process("任务 %s 的duration应为非负数" % name)
            if not isinstance(rate, (int, float)) or not 0 <= rate <= 1:
                error_process("任务 %s 的success_rate应为0~1中的数字" % name)
            if not isinstance(dependence, list) or not all(isinstance(d, str) for d in dependence):
                error_process("任务 %s 的dependencies应为字符串列表" % name)
            t = Task(name=name, duration=float(duration), success_rate=float(rate),
                     dependencies=list(dict.fromkeys(dependence)))
            Tasks[t.name] = t
        for name, t in Tasks.items():       #依赖检验
            for d in t.dependencies:
                if d not in Tasks:
                    error_process("任务 %s 依赖的前置任务 %s 不存在" % (name, d))
        if timeout is not None:
            if not isinstance(timeout, (int, float)) or timeout <= 0:
                error_process("timeout应为正数")
        order = Kahn_sort(Tasks)   # 【新增】拓扑排序 + 依赖环检测
        return timeout, order, Tasks
    except FileNotFoundError:
        error_process("配置文件不存在：%s" % config)
    except json.decoder.JSONDecodeError:
        error_process("JSON 配置文件语法出错")
    except yaml.YAMLError:
        error_process("YAML 配置文件语法出错")
    except KeyError as e:
        error_process("配置文件缺少字段：%s" % e)
    except ValueError as e:
        error_process("配置文件字段值出错：%s" % e)
    except Exception as e:
        error_process("配置文件出错：%s" % e)

#命令行输入处理
def command_process():
    global report_json
    parser = argparse.ArgumentParser()
    parser.add_argument("--config")
    parser.add_argument("--timeout", type=float, default=None)
    parser.add_argument("--report", type=str,default="report.json")
    parser.add_argument("--seed", type=int, default=None)
    args = parser.parse_args()
    if not args.config:
        error_process("命令行缺少--config配置文件路径")
    config = args.config
    config_timeout, order, Tasks = read_request(config)
    if args.timeout is not None:
        timeout = args.timeout
    else:
        timeout = config_timeout
    if timeout is not None and timeout <= 0:
        error_process("timeout应为正数")
    report_json = args.report
    return config, timeout, args.seed, order, Tasks

def task_process(order, Tasks, timeout, start_time):
    for key in order:
        task = Tasks[key]
        timeout_test(time.time() - start_time, timeout, key, 0, None)
        if any(Tasks[dep].status in ("SKIPPED", "FAILED") for dep in task.dependencies):
            task.success = 2
            task.status = "SKIPPED"
            print(key, end=" ")
            command_output("SKIPPED")
            report["tasks"].append({
                "name": key, "status": "SKIPPED", "attempts": 0,
                "duration": 0.0, "started_at": None, "ended_at": None,
            })
            continue
        started_at = time.time()
        status, attempts = success_calculate(task, started_at, start_time, timeout)
        ended_at = time.time()
        task.success = 1 if status == "SUCCESS" else 2
        task.status = status if status == "SUCCESS" else "SKIPPED"
        print(key, end=" ")
        command_output(task.status)
        report["tasks"].append({
            "name": key, "status": task.status, "attempts": attempts,
            "duration": round(ended_at - started_at, 2),
            "started_at": round(started_at, 2),
            "ended_at": round(ended_at, 2),
        })

def report_writer(report_json):
    try:
        with open(report_json, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
    except PermissionError:
        error_process("目标文件被占用或权限不足")
    except OSError:
        error_process("写入目标json文件失败")

def main():
    start_time = time.time()
    config, timeout, seed, order, Tasks = command_process()
    if seed is not None:
        random.seed(seed)
    try:
        task_process(order, Tasks, timeout, start_time)
    except task_timeout_process as e:
        now = time.time()
        report["timeout"] = True
        Tasks[e.key].status = "TIMEOUT"
        print(e.key, end=" ")
        command_output("FAILED")
        if e.started_at is not None:
            report["tasks"].append({
                "name": e.key, "status": "TIMEOUT", "attempts": e.attempts,
                "duration": round(now - e.started_at, 2),
                "started_at": round(e.started_at, 2), "ended_at": round(now, 2),
            })
        else:
            report["tasks"].append({
                "name": e.key, "status": "TIMEOUT", "attempts": 0,
                "duration": 0.0, "started_at": None, "ended_at": None,
            })
        done = {t["name"] for t in report["tasks"]}#-----------------------------------------------------
        for name in Tasks:
            if name not in done:
                Tasks[name].status = "TIMEOUT"
                report["tasks"].append({
                    "name": name, "status": "TIMEOUT", "attempts": 0,
                    "duration": 0.0, "started_at": None, "ended_at": None,
                })
        report["total_duration"] = round(time.time() - start_time, 2)
        report_writer(report_json)
        sys.exit(0)
    report["total_duration"] = round(time.time() - start_time, 2)
    report_writer(report_json)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n已手动中断", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        error_process("运行出错：%s" % e)