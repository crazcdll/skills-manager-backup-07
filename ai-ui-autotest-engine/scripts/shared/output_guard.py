#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""输出边界守卫：脱敏 + 零拷贝归档。

**边界原则：只在「离开运行态」时脱敏。**
运行态的 `flow-context.json` / `intake.json` 必须保留原值——登录动作与
`{password}` 占位符依赖它；一旦就地改写，C2 之后的步骤会拿到 `***`。

统一出口（全部经过本模块）：
  1. 报告落盘（run / case 的 report.json）
  2. 平台上报（transport.insert_report）
  3. 归档目录（archive_run 复制完成后整树扫描）
  4. 控制台遥测（console/telemetry.py 的行级过滤）
  5. 命令回显（input-seed / input-answer 的 JSON 输出）

脱敏双保险：
  · **已知 secret 值精确替换**（含 JSON 转义形态）——覆盖 secret 被拼进
    字符串的场景（steps.jsonl 的 note 内嵌 JSON、landing_scheme 等）；
  · **按 key 的正则掩码**——覆盖值未知的日志行（如 `--password xxx`）。

过程信息（inspect_tree / dumps / record_data / mock_baseline / tmp）不删：
迭代期需要复盘执行链路，归档只做脱敏，不做白名单裁剪。
"""
import json
import os
import re
import stat

MASK = "***"
# 精确值替换的最低长度：避免 4 位密码/验证码这类短值误伤时间戳等无关文本；
# 短值仍会被下面的 key 正则按字段掩码。
_MIN_SECRET_LEN = 6

_SECRET_KEY_PARTS = (
    "password", "passwd", "pwd", "token", "cookie",
    "authorization", "secret", "credential",
)
_KEY_PAIR_RE = re.compile(
    r'(?i)(["\'](?:password|passwd|pwd|_password_raw|token|cookie|authorization|secret|credential)["\']\s*:\s*)'
    r'(["\'])([^"\']*)\2'
)
# steps.jsonl 的 note 是「JSON 字符串里的 JSON」：key/quote 都带反斜杠转义
_ESCAPED_KEY_PAIR_RE = re.compile(
    r'(?i)(\\?["\'](?:password|passwd|pwd|_password_raw|token|cookie|authorization|secret|credential)'
    r'\\?["\']\s*:\s*\\?["\'])([^"\'\\]*)(\\?["\'])'
)
_CLI_FLAG_RE = re.compile(
    r'(?i)(--?(?:password|passwd|pwd|token|cookie|secret)(?:=|\s+))(\S+)'
)
# 通用「key=value / key: value」形态：query string、YAML、shell 变量等非 JSON 场景。
# 精确值替换有长度下限（短密码不参与），这条兜住短值。
_KEY_VALUE_RE = re.compile(
    r'(?i)(\b(?:password|passwd|pwd|token|secret|credential)\b\s*[=:]\s*)'
    r'(?![*"\'\\])([^\s&,;"\'\}\]\)]+)'
)
# 认证头 / Cookie 的值自带空格（`Bearer <jwt>`、`a=b; c=d`）：整行掩码
_HEADER_RE = re.compile(
    r'(?i)(\b(?:cookie|set-cookie|authorization)\b\s*:\s*)([^\r\n]+)'
)

# 二进制 / 压缩包不参与文本脱敏；归档时它们内容不可变，恰好也是可以零拷贝硬链的集合
_SKIP_EXT = {
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".zip", ".gz", ".tar",
    ".mp4", ".mov", ".pdf", ".apk", ".ipa", ".so", ".dylib", ".jar",
}


def _is_secret_key(key) -> bool:
    k = str(key).lower().replace("-", "_")
    return any(part in k for part in _SECRET_KEY_PARTS)


def _collect_strings(value, found):
    if isinstance(value, str):
        if len(value) >= 4:
            found.add(value)
    elif isinstance(value, dict):
        for item in value.values():
            _collect_strings(item, found)
    elif isinstance(value, (list, tuple)):
        for item in value:
            _collect_strings(item, found)


def secrets_from(obj) -> set:
    """递归收集敏感 key 下的字符串值，供整树精确替换使用。"""
    found = set()
    _walk_secrets(obj, found)
    return found


def _walk_secrets(obj, found):
    if isinstance(obj, dict):
        for key, value in obj.items():
            if _is_secret_key(key):
                _collect_strings(value, found)
            else:
                _walk_secrets(value, found)
    elif isinstance(obj, (list, tuple)):
        for item in obj:
            _walk_secrets(item, found)


def redact_text(text, secrets=()):
    """对单段文本做脱敏（已知值精确替换 + key 正则掩码）。"""
    if not isinstance(text, str) or not text:
        return text
    out = text
    for secret in secrets or ():
        if not isinstance(secret, str) or len(secret) < _MIN_SECRET_LEN:
            continue
        out = out.replace(secret, MASK)
        escaped = json.dumps(secret, ensure_ascii=False)[1:-1]
        if escaped and escaped != secret:
            out = out.replace(escaped, MASK)
    out = _HEADER_RE.sub(lambda m: f"{m.group(1)}{MASK}", out)
    out = _KEY_PAIR_RE.sub(
        lambda m: f"{m.group(1)}{m.group(2)}{MASK}{m.group(2)}", out
    )
    out = _ESCAPED_KEY_PAIR_RE.sub(
        lambda m: f"{m.group(1)}{MASK}{m.group(3)}", out
    )
    out = _KEY_VALUE_RE.sub(lambda m: f"{m.group(1)}{MASK}", out)
    out = _CLI_FLAG_RE.sub(lambda m: f"{m.group(1)}{MASK}", out)
    return out


def redact_obj(obj, secrets=None):
    """递归脱敏内存对象；字符串值额外做行级掩码。"""
    secrets = tuple(secrets or ())
    if isinstance(obj, dict):
        result = {}
        for key, value in obj.items():
            if _is_secret_key(key) and _is_scalar(value):
                result[key] = MASK if value not in ("", None) else value
            else:
                result[key] = redact_obj(value, secrets)
        return result
    if isinstance(obj, list):
        return [redact_obj(item, secrets) for item in obj]
    if isinstance(obj, str):
        return redact_text(obj, secrets)
    return obj


def _is_scalar(value) -> bool:
    # bool 不是「值型凭证」：`is_password_reset: true` 这类字段不能被改成字符串 "***"
    return isinstance(value, (str, int, float)) and not isinstance(value, bool)


def _write_atomic(path, text):
    """保留原权限的原子覆盖：不破坏归档硬链接（新 inode 替换目录项）。"""
    try:
        mode = stat.S_IMODE(os.stat(path).st_mode)
    except OSError:
        mode = 0o644
    tmp = f"{path}.redact.tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(text)
    os.chmod(tmp, mode)
    os.replace(tmp, path)


def redact_tree(root, secrets=()):
    """整树脱敏（就地、原子替换）；返回实际改写的文件列表。"""
    secrets = tuple(secrets or ())
    changed = []
    for dirpath, _dirnames, filenames in os.walk(root):
        for name in filenames:
            path = os.path.join(dirpath, name)
            if os.path.islink(path) or not os.path.isfile(path):
                continue
            ext = os.path.splitext(name)[1].lower()
            if ext in _SKIP_EXT:
                continue
            try:
                with open(path, "rb") as fh:
                    raw = fh.read()
            except OSError:
                continue
            if b"\x00" in raw:
                # 未知扩展名的二进制（db / 字体 / 私有格式）：按字节判定，避免被当文本重写
                continue
            try:
                text = raw.decode("utf-8")
            except UnicodeDecodeError:
                continue
            redacted = redact_text(text, secrets)
            if redacted != text:
                _write_atomic(path, redacted)
                changed.append(path)
    return changed


def link_or_copy(src, dst):
    """同盘硬链（不占额外字节）；跨盘或文件系统不支持时回退复制。"""
    try:
        os.link(src, dst)
        return dst
    except OSError:
        import shutil
        return shutil.copy2(src, dst)


def copy_for_archive(src, dst):
    """归档复制策略：媒体/二进制零拷贝硬链，**文本一律复制**。

    归档必须是一次运行的不可变快照。文本文件（尤其 workspace 级的
    `console-ingest.jsonl` 这类 append-only 日志）在后续 run 中可能被继续追加，
    一旦硬链共享 inode，历史归档就会随源文件漂移。文本体积远小于截图，
    复制的成本可以忽略。
    """
    if os.path.splitext(src)[1].lower() in _SKIP_EXT:
        return link_or_copy(src, dst)
    import shutil
    return shutil.copy2(src, dst)
