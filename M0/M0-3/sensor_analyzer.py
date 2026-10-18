#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sensor_analyzer.py  —— 上一届学长留下的"能用"的脚本

注释（学长原话）：
    "处理一下传感器数据就能用"

原本意图：
    1. 读取 sensor_data.csv（列：time, value）
    2. 计算 value 的平均值、标准差
    3. 剔除离群值（|value - mean| > 2 * std）
    4. 把清洗后的数据保存为 cleaned_data.csv
    5. 打印一份统计摘要

现状：跑不通 / 跑出来数不对。就交给你了。
"""
import argparse
import csv
import os
import sys

data = []
times = []
cleaned = []
#添加命令行输入命令的处理
def command_input():
    INPUT_FILE = "sensor_data.csv"
    OUTPUT_FILE = "cleaned_data.csv"
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default=INPUT_FILE)
    parser.add_argument("--output", default=OUTPUT_FILE)
    args = parser.parse_args()
    INPUT_FILE = args.input
    OUTPUT_FILE = args.output
    return INPUT_FILE, OUTPUT_FILE
def err_output(error):
    print(error,file=sys.stderr)
    sys.exit(1)

# --- 读取数据 ---
#改用with嵌套
#添加常见错误处理
def read_input(INPUT_FILE, OUTPUT_FILE):
    try:
        with open(INPUT_FILE, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                t = float(row["time"])
                v = float(row["value"]) #修正键名
                times.append(t)
                data.append(v)
    except FileNotFoundError:
        err_output("目标csv文件不存在")
    except ValueError:
        err_output("目标csv文件字典值出错")
    except KeyError:
        err_output("目标csv文件字典键出错")
    except Exception:
        err_output("目标csv文件出现错误")
    print("共读取 %d 条数据" % len(data))
def calculate(data):
    if not data:
        err_output("目标csv文件为空")
    if len(data) == 0:
        err_output("出现除0错误")
    #计算平均值
    total = 0
    for v in data:
        total += v
    mean = total / len(data)
    # --- 计算标准差 ---
    acc = 0
    for v in data:
        acc += (v - mean) ** 2  # 标准差计算方法纠正
    std = (acc / len(data)) ** 0.5
    return mean,std
# --- 剔除离群值 ---
def info_process(data,mean,std):
    for i,v in enumerate(data):
        if abs(v - mean) <=  2 * std: #添加下界判断
            cleaned.append((times[i],v))
# --- 输出清洗后的数据 ---
def process_output(OUTPUT_FILE):
    output_path = OUTPUT_FILE#修正目录
    # 改用with嵌套
    # 添加错误处理
    try:
        with open(output_path, "w", newline="",encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["time", "value"])
            for t,v in cleaned:
                writer.writerow([t,v])
            return output_path
    except OSError:
        err_output("系统出错，文件无法正常写入")
def main():
    print("=== 传感器数据分析 ===")
    INPUT_FILE, OUTPUT_FILE = command_input()
    read_input(INPUT_FILE, OUTPUT_FILE)
    mean,std = calculate(data)
    info_process(data,mean,std)
    output_path = process_output(OUTPUT_FILE)
    print("均值 mean = %.4f" % mean)
    print("标准差 std = %.4f" % std)
    print("清洗后剩余 %d 条" % len(cleaned))
    print("已保存到 %s" % output_path)
if __name__ == "__main__":
    main()