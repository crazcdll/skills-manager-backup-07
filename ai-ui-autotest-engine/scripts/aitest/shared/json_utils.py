import json
import os


def _replace_json(path, data):
    """同目录唯一临时文件 → os.replace（并发安全）。

    临时文件名必须带 pid：固定 `<path>.tmp` 时两个进程会同时写同一个临时文件，
    先 replace 的进程会把文件挪走，后一个 replace 直接
    `FileNotFoundError: ... .tmp -> ...`（实测并发冷启动必现）。
    """
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = f"{path}.{os.getpid()}.tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass


def write_json_atomic(path, data):
    """原子写 JSON（同目录唯一临时文件 + os.replace）。

    刻意**不做**「先创建空文件占位并打印提示」：没有调用方依赖占位，而 print 会污染
    那些 stdout 是 JSON 的命令（check-deps 等），把产物直接变成非法 JSON。
    """
    _replace_json(path, data)


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
