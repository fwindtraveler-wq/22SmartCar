## M0-3问题报告
## 1. 第 37 行：字典键名大小写错误
- **问题**：取值时写成 `row["Value"]`，而 CSV 表头是 `value`。
- **现象**：运行时抛 `KeyError: 'Value'`，脚本在读取阶段即中断。
- **原因**：CSV 表头与代码中的键名大小写不一致，`DictReader` 的键严格区分大小写。
- **解决**：改为 `row["value"]`。

```python
# 修复后
v = float(row["value"])
```

## 2. 第 28、65—66 行：`cleaned` 列表从未被填充
- **问题**：`cleaned = []` 初始化后，全程没有任何 `cleaned.append(...)`，但输出时直接 `for v in cleaned:`。
- **现象**：输出文件只有表头没有数据，控制台打印「清洗后剩余 0 条」。
- **原因**：`cleaned` 始终是空列表，写文件的循环一次都不会执行。
- **解决**：在筛选离群值的循环中把保留项 `(t, v)` 加入 `cleaned`，再基于它写文件。

```python
# 修复后
cleaned.append((t, v))
```

## 3. 第 56—58 行：遍历列表的同时删除元素
- **问题**：`for v in data:` 循环体内部执行 `data.remove(v)`，原地修改正在遍历的列表。
- **现象**：离群值可能漏删，或删除后跳过后续元素，导致清洗结果条数不对、统计结果不稳定。
- **原因**：列表迭代器按索引向后推进；删除当前元素后后面的元素整体前移，下一次迭代会跳过紧跟在被删元素之后的那个元素。
- **解决**：不要边遍历边删除。改为构造新列表保存保留项（如 `cleaned.append((t, v))`），或使用列表推导式 / 倒序遍历删除。

```python
# 修复后
cleaned = []
for t, v in data:
    if abs(v - mean) <= 2 * std:
        cleaned.append((t, v))
```

## 4. 第 61 行：输出路径拼接错误且未创建目录
- **问题**：`output_path = os.path.join("/", OUTPUT_DIR, OUTPUT_FILE)`。
- **现象**：文件被写到根目录的 `/out/cleaned_data.csv`，常见报错 `FileNotFoundError` 或 `PermissionError`；即使写成功，也不是项目当前目录下的 `out/cleaned_data.csv`。
- **原因**：`os.path.join("/", ...)` 的第一个参数是绝对路径 `/`，后续参数会被拼接成绝对路径；同时代码没有提前创建 `out` 目录。
- **解决**：改为相对路径拼接，并先创建输出目录，文件句柄用 `with` 管理。

```python
# 修复后
os.makedirs(OUTPUT_DIR, exist_ok=True)
output_path = os.path.join(OUTPUT_DIR, OUTPUT_FILE)
with open(output_path, "w", newline="", encoding="utf-8") as f:
    ...
```

## 5. 第 52—53 行：标准差计算公式错误
- **问题**：离差平方的累加与开方写法有误。
- **现象**：标准差数值错误，进一步导致离群值筛选阈值失真。
- **原因**：对标准差公式 `sqrt(Σ(v - mean)² / n)` 的展开理解有误。
- **解决**：
  
```python
# 修复后
acc = 0.0
for v in values:
    acc += (v - mean) ** 2
std = (acc / len(values)) ** 0.5
```

## 6. 第 57 行：离群值只判上界，未处理下界
- **问题**：`if v > mean + 2 * std:` 只判断了大于上界的情况。
- **现象**：明显偏大的值被剔除，但明显偏小的离群值（`v < mean - 2 * std`）仍被保留，清洗不完整。
- **原因**：原意是 `|value - mean| > 2 * std`，应同时覆盖均值两侧；当前只比较单侧，漏掉下界。
- **解决**：改为按绝对值判断的保留条件。

```python
# 修复后
if abs(v - mean) <= 2 * std:
    cleaned.append((t, v))
```

## 7. 第 64—66 行：表头与数据列数不一致，且丢失 `time`
- **问题**：表头写 `writer.writerow(["time", "value"])`，数据行却是 `writer.writerow([v])`。
- **现象**：`cleaned_data.csv` 每行只有 `value` 没有 `time`，表头两列、数据一列，列数不匹配，下游解析容易错位。
- **原因**：`writer.writerow([v])` 只写一个字段，`time` 没有参与清洗后的输出；若 `cleaned` 只存 `value`，也无从恢复对应时间。
- **解决**：清洗时保存 `(t, v)` 配对，写出时整行写入。

```python
# 修复后
writer.writerow(["time", "value"])
for t, v in cleaned:
    writer.writerow([t, v])
```

## 8. 第 47 行：计算均值前未检查空数据
- **问题**：`mean = total / len(data)` 直接除以 `len(data)`。
- **现象**：若 `sensor_data.csv` 为空或无有效数据，抛 `ZeroDivisionError: division by zero`，程序崩溃。
- **原因**：空列表的 `len(data)` 为 0，Python 不允许除以 0。
- **解决**：读取完成后先判空，再计算均值与标准差。

```python
# 修复后
if not data:
    print("无有效数据")
    return
```