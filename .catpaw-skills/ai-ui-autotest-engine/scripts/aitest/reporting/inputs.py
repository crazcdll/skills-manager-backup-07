#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""输入制品化：把冻结的输入复制进 Case 报告包，并投影成上报 payload 的 `inputs[]`。

口径（与截图 frames 完全一致）
------------------------------
1. **报告包自包含**：`<batch>/<case_tag>/inputs/<name>` —— 与 `frames/` 同级，本机可直接
   打开审计，随报告一起归档、一起被清理；
2. **正文内联**：`content` 带上完整 JSON，平台 / 他人跨机打开报告即可阅读，不依赖对象存储，
   也不要求执行机在线；
3. **路径 + 大小**：`artifact_path`（报告包相对路径）用于定位，`size_bytes` 只描述
   内容量级，不做任何跨文件指纹比对。

读取口径：**纯读 workspace 冻结副本**（`shared/input_freeze.py` 在 `steps-generate` 写入），
不回读上游 `.docs/` / `.orchestration/`（那两处按 keep-latest-N 滚动清理，随时可能 404）。
"""
import os
import shutil

from aitest.shared import input_freeze
from aitest.shared.output_guard import redact_text, secrets_from

INPUTS_PKG_DIRNAME = "inputs"


def _read_text(path):
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as handle:
            return handle.read()
    except OSError as error:
        print(f"  ⚠️ 读取输入原文失败 {os.path.basename(path)}: {error}")
        return ""


def _publish(case_tag, output_dir, name, source_path, kind, source_label, secrets):
    """把一个输入文件复制进报告包，并返回 payload 条目。"""
    package_dir = os.path.join(output_dir, INPUTS_PKG_DIRNAME)
    os.makedirs(package_dir, exist_ok=True)
    destination = os.path.join(package_dir, name)
    try:
        if os.path.abspath(source_path) != os.path.abspath(destination):
            # 文本一律复制：workspace 后续可能被清理，硬链会让报告包随源文件一起消失
            shutil.copy2(source_path, destination)
    except OSError as error:
        print(f"  ⚠️ 输入复制进报告包失败 {name}: {error}")

    content = _read_text(source_path)
    if content:
        content = redact_text(content, secrets)
    entry = {
        "kind": kind,
        "name": name,
        "artifact_path": f"{case_tag}/{INPUTS_PKG_DIRNAME}/{name}",
        "source_path": source_label,
        "size_bytes": os.path.getsize(source_path) if os.path.isfile(source_path) else 0,
        "content_inline": bool(content),
        "content": content,
    }
    if entry["size_bytes"] > input_freeze.INLINE_HINT_BYTES:
        print(f"  ⚠️ 输入过大（{name}: {entry['size_bytes']} bytes）已内联，"
              "注意报告体积与平台请求体上限")
    return entry


def materialize_inputs(manifest, context, output_dir):
    """为当前 Case 生成 `inputs[]`（业务真源 + 执行输入），并复制进报告包。

    返回按 `steps_json` → `steps_input` 排序的列表；任一文件缺失只警告不中断上报。
    """
    case_id = str(manifest.get("case_id") or "")
    case_tag = str(manifest.get("case_tag") or "case")
    env = context.get("env") or {}
    secrets = tuple(secrets_from(env))

    entries = []

    frozen = input_freeze.find_manifest(case_id)
    business = input_freeze.manifest_file(frozen, "steps_json")
    if business:
        steps_path = business.get("abs_path") or ""
        if os.path.isfile(steps_path):
            entries.append(_publish(
                case_tag, output_dir, input_freeze.STEPS_JSON_NAME,
                steps_path, "steps_json", business.get("source_path") or steps_path,
                secrets,
            ))
        else:
            print(f"  ⚠️ 业务真源冻结副本缺失: {steps_path}")
    else:
        print(f"  ⚠️ 未找到 case {case_id} 的输入冻结清单（报告将不含业务 steps.json）")

    # 执行输入：优先取 flow-init 解析后的 steps-input.json（真正被执行的占位符取值）
    exec_path = str(context.get("meta", {}).get("steps_json_path") or "")
    if exec_path and os.path.isfile(exec_path):
        entries.append(_publish(
            case_tag, output_dir, input_freeze.STEPS_INPUT_NAME,
            exec_path, "steps_input", exec_path, secrets,
        ))
    else:
        print(f"  ⚠️ 执行输入缺失: {exec_path}")

    return entries
