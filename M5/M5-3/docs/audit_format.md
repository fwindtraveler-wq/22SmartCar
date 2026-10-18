# 审计日志字段与哈希链

每行是一条 JSON：

```json
{"ts":"2026-09-22T15:30:12.345","op":"MODEL_SWITCH","from":"yolov8n_fp32","to":"yolov8n_int8","source":"ui","user":"operator","result":"ok","prev_hash":"a1b2...","hash":"c3d4..."}
```

- `prev_hash`：上一条日志的 SHA-256，第一条固定为 64 个 0。
- `hash`：对当前行去掉 `hash` 字段后的规范 JSON 计算 SHA-256。
- 同目录的 `.meta.json` 保存行数和最终哈希，用于检测“删除最后一行”。

`tools/verify_audit.py` 会逐行验证前后哈希和最终元数据。
