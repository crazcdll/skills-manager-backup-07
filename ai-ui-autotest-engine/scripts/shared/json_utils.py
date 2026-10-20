import json
import os


def write_json_atomic(path, data):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    # 1. 先创建空文件（占位），确保文件在写入前已存在
    if not os.path.exists(path):
        with open(path, "w", encoding="utf-8") as f:
            pass
        print(f"  ⚪ 空文件已创建: {path}")
    # 2. 再写入完整内容（原子写入：先写 .tmp 再替换，避免写半截）
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def write_json_atomic_quiet(path, data):
    """原子写入 JSON 的**静默变体**：不预留空文件占位、不打印任何提示。

    与 `write_json_atomic` 的唯一差异：后者在文件不存在时会先创建一个空文件并打印
    「空文件已创建」——那套行为适用于「需要让文件先出现」的流程；而纯机器状态 / 缓存
    （常被会向 stdout 输出 JSON 的命令内联调用）既不需要占位，其提示还会污染 stdout
    （调用方需按 JSON 解析输出）。因此这类写入统一走本函数。
    """
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def read_json(path, default=None):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {} if default is None else default


def read_jsonl(path):
    records = []
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(record, dict):
                    records.append(record)
    except OSError:
        pass
    return records
