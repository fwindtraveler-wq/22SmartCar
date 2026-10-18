import argparse
import csv
import math
import os
import sys
import yaml

DEFAULT_PATH = "config.yaml"
#设置错误处理模块
def err_output(error):
    print(error,file=sys.stderr)
    sys.exit(1)
#命令行传参初始化
def command_line_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config",
        default=DEFAULT_PATH,
    )
    return parser
#yaml文件检查
def yaml_check(path):
    if not os.path.exists(path):
        err_output("目标yaml文件不存在")
    try:
        with open(path, encoding="utf-8") as f:
            data_index = yaml.safe_load(f)
    except yaml.YAMLError:
        err_output("配置文件错误")
    except  UnicodeDecodeError:
        err_output("目标yaml文件编码有误，为非utf-8编码")
    if not isinstance(data_index, dict):
        err_output("配置文件错误")
    return data_index
#获取csv文件目录
def csv_path_get(data_index):
    for key in data_index:
        if key == "input_csv":
            return data_index[key]
    return None
#检查csv文件内容
def csv_check():
    parser = command_line_args()
    args = parser.parse_args()
    data_index = yaml_check(args.config)
    csv_path = csv_path_get(data_index)
    if not isinstance(csv_path, str) :
        err_output("目标csv路径出错")
    #绝对路径转化
    if not os.path.isabs(csv_path):
        csv_path = os.path.join(os.path.dirname(os.path.abspath(args.config)), csv_path)
    if not os.path.exists(csv_path):
        err_output("csv文件路径错误")
    columns = data_index.get("columns")
    if not isinstance(columns, dict) or "x" not in columns or "y" not in columns:
        err_output("csv文件列名不匹配")
    col_x=columns["x"]
    col_y=columns["y"]
    verbose = True
    task=data_index.get("task")
    if isinstance(task, dict) and "verbose" in task:
        verbose = bool(task["verbose"])
    return col_x, col_y,csv_path,verbose
#读取csv文件内容
def csv_reader(col_x, col_y, csv_path):
    xs=[]
    ys=[]
    try:
        with open(csv_path, encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames
            if not fieldnames:
                err_output("csv文件缺少文件表头")
            for i in (col_x, col_y):
                if i not in fieldnames:
                    err_output("csv文件缺少列")
            for row in reader:
                try:
                    x = (float(row[col_x]))
                    y = (float(row[col_y]))
                except (ValueError, TypeError):
                    err_output("目标csv数据有误")
                if not math.isfinite(x) or not math.isfinite(y):
                    err_output("csv文件中存在inf/nan")
                xs.append(x)
                ys.append(y)
    except UnicodeDecodeError:
        err_output("目标csv文件编码错误（非utf-8编码）")
    return xs, ys
#计算核心
def calculate(xs,ys,verbose):
    if len(xs) == 0:
        err_output("目标csv文件为空")
    sum_x=0
    sum_y=0
    for i in range(len(xs)):
        sum_x+=xs[i]
        sum_y+=ys[i]
    mean_x=sum_x/len(xs)
    mean_y=sum_y/len(ys)
    dx=0.0
    dy=0.0
    prod=0.0
    for i in range(len(xs)):
        dx += (xs[i]-mean_x)**2
        dy += (ys[i]-mean_y)**2
        prod += (xs[i]-mean_x)*(ys[i]-mean_y)
    demon=dx*dy
    if demon == 0:
        err_output("相关系数无意义")
    r = prod / math.sqrt(demon)
    #判断是否需要输出中间量
    if verbose:
        print("n=",len(xs))
        print("mean_x=",mean_x)
        print("mean_y=",mean_y)
    print("r=",r)
#主执行函数
def main():
    col_x,col_y,csv_path,verbose = csv_check()
    xs, ys = csv_reader(col_x, col_y, csv_path)
    calculate(xs,ys,verbose)
if __name__ == "__main__":
    main()