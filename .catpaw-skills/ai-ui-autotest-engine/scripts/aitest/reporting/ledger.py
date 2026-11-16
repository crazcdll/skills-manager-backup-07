#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""报告增量上报台账：把「哪些 Case 已经 append 成功、本 run 是否已收尾」落在本地。

为什么需要台账（而不是每次重发全量）：
  · **幂等**：C5_report 与 flow-finalize 都可能触发上报（重试 / 异常收尾），
    平台按 case_id 幂等，但重复发送仍然白费带宽；
  · **可补传**：单 Case 追加失败（网络抖动）不应阻塞执行，收尾时只补传台账里
    缺失的 Case —— 每次仍是一个 Case 的 payload；
  · **Close 语义**：平台把 `cases[0]` 当行级视图，收尾必须重发本 run 的首个 Case
    才能写入最终 run_status；台账记录它上一次的 run_status，避免无意义的重复发送。

文件位置：`<batch_output_dir>/report-upload.json`（每个 shard 独立目录，互不干扰）。

`opened` 记录「本 run 的报告行已由引擎踩过 Open」：重复 flow-init（调试/重跑）不会
再次整行 UPSERT 抹掉已追加的 Case。
"""
import os

from aitest.shared.json_utils import read_json, write_json_atomic

FILENAME = "report-upload.json"
SCHEMA_VERSION = 1


def path(output_dir):
    return os.path.join(output_dir, FILENAME)


def load(output_dir):
    """读取台账；缺失/损坏时返回空台账（等价于「一条都没传过」）。"""
    data = read_json(path(output_dir), default={}) or {}
    cases = data.get("cases")
    return {
        "schema_version": SCHEMA_VERSION,
        "report_id": str(data.get("report_id") or ""),
        "cases": cases if isinstance(cases, dict) else {},
        "opened": bool(data.get("opened")),
        "closed": bool(data.get("closed")),
    }


def save(output_dir, data):
    write_json_atomic(path(output_dir), data)


def mark_opened(output_dir, report_id):
    data = load(output_dir)
    data["report_id"] = str(report_id)
    data["opened"] = True
    save(output_dir, data)
    return data


def mark_case(output_dir, report_id, case_id, run_status):
    """记录某 Case 已按该 run_status 成功追加。"""
    data = load(output_dir)
    data["report_id"] = str(report_id)
    data["cases"][str(case_id)] = {"run_status": run_status}
    save(output_dir, data)
    return data


def mark_closed(output_dir, report_id):
    data = load(output_dir)
    data["report_id"] = str(report_id)
    data["closed"] = True
    save(output_dir, data)
    return data


def uploaded_run_status(output_dir, case_id):
    """该 Case 上一次成功上报时的 run_status（未上报返回 None）。"""
    entry = load(output_dir)["cases"].get(str(case_id))
    return entry.get("run_status") if isinstance(entry, dict) else None
