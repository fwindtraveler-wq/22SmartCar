import sys
sys.path.append("..")
from legacy_corr import calculate
if __name__ == "__main__":
    try:
        choice = int(input("请输入要测试的选项：1，正常数据1、2。正常数据2、3.异常数据——0方差"))
    except ValueError:
        print("请输入1-3的整数选择测试对象",file=sys.stderr)
        sys.exit(1)
    match choice:
        case 1:
            xs = [1,2,3]
            ys = [2,4,6]
        case 2:
            xs = [1,2,3]
            ys = [6,4,2]
        case 3:
            xs = [0,0,0]
            ys = [0,0,0]
        case _:
            print("请输入1-3的整数选择测试对象",file=sys.stderr)
            sys.exit(1)
    calculate(xs,ys,True)