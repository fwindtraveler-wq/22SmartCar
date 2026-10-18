### M0-2程序要求：
## 运行方式：
1. 在命令行中直接使用 python3 legacy_corr.py --config 配置文件（yaml文件）进行，默认config为config.yaml
2. 运行正常回直接将结果输出到stdout，否则会将报错原因输出至stderr
## 输入文件格式要求：
# 对于yaml文件：
1. 包含input_csv 即csv的文件名
2. 包含columns 指明x,y对应的参数名
3. 包含task 里面包含name 即任务名，以及verbose（要求为布尔值）来指明要不要详细输出参数
4. yaml文件应符合python中字典的格式规范
5. 采用utf-8编码
# 对于csv文件：
1. 表头不应为空
2. 列名:sensor_a,sensor_b,timestamp,note,不少列
3. sensor_a与sensor_b的数据类型应为float
4. 数据中不含inf/nan
5. 采用utf-8编码
6. 数据不为空
## 输出结果：
1. n为样本量
2. mean前缀的为平均数
3. r为相关系数
4. r > 0是数据为正相关，r < 0时为负相关。|r|越趋近于1，数据的相关性越强
## AI使用情况
> 主要找找各种异常情况名称