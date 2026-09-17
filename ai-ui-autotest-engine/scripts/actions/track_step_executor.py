#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""埋点步骤独立执行器：录制数据快照 → lx0 解析 → match 匹配 → 提取关键字段值。

不执行程序化断言，所有埋点字段拍平为点号路径格式，由 AI 通过 override-step-result 判定。
如果用户配置了 expected_fields，AI 会基于证据文件中的 extracted_fields 逐字段判定。
"""
import os
import time

from core.util.json_utils import write_json_atomic
from core.errors import FlowStateError, StepAssertionError, soft_fail

from core.util.case_utils import resolve_mis
from core.flow.step_scheduler import update_step_result as fc_update_step
from core.audit.runtime_audit import append_event
from core.util.records import StepRecord, SRC_STEP, SHOT_STEP, frame_path
from mock.appmock_record import appmock_record_data
from assertions.data.track import (
    extract_lx0_items, parse_events, match_events,
    _collect_val_lab_layers, _create_track_mock,
)
from assertions.utils.truncate import truncate_values
from context import get_platform_ops


def _save_evidence(case_ws, sid, event, layers, extracted_fields, expected_fields=None):
    """将结构化证据写入独立文件 track_evidence_<sid>.json，供 AI 读取分析。

    包含原始事件数据、拍平后的字段和待校验的字段清单（expected_fields），
    AI 优先读取 extracted_fields 做判定。
    """
    if not case_ws:
        return None
    diag_dir = os.path.join(case_ws, "diagnostics")
    os.makedirs(diag_dir, exist_ok=True)
    path = os.path.join(diag_dir, f"track_evidence_{sid}.json")
    payload = {
        "event": event,
        "layers": layers,
        "extracted_fields": extracted_fields,
    }
    if expected_fields:
        payload["expected_fields"] = expected_fields
    try:
        write_json_atomic(path, payload)
        return path
    except Exception as e:
        print(f"  ⚠️ 证据文件保存失败: {e}")
        return None


def _save_parsed_events(case_ws, sid, events):
    """保存扁平化解析后的事件列表到 diagnostics/track_events_<sid>.json。

    所有埋点断言（匹配、AI 判定）均基于此文件处理，是埋点测试的权威中间产物。
    """
    if not case_ws or not events:
        return None
    diag_dir = os.path.join(case_ws, "diagnostics")
    os.makedirs(diag_dir, exist_ok=True)
    path = os.path.join(diag_dir, f"track_events_{sid}.json")
    try:
        write_json_atomic(path, events)
        print(f"  📋 扁平化事件列表: {path} ({len(events)} 条)")
        return path
    except Exception as e:
        print(f"  ⚠️ 扁平化事件保存失败: {e}")
        return None


def _fetch_and_match_event(mis, assertion, timeout_sec, case_ws=None, sid=None):
    deadline = time.time() + timeout_sec
    attempt = 0
    events = []
    while True:
        attempt += 1
        data = appmock_record_data(
            auto_filter=True, save_path=None, mis=mis, exclude_noise=False,
        )
        items = data.get("items", []) if data else []
        lx0_items = extract_lx0_items(items)
        events, event_to_item = parse_events(lx0_items)
        matched = match_events(events, assertion)
        if matched:
            m = matched[-1]
            event = m["event"]
            idx = events.index(event)
            source_item = event_to_item[idx] if idx < len(event_to_item) else None
            # 匹配成功后保存扁平化事件列表
            _save_parsed_events(case_ws, sid, events)
            return event, source_item, events, attempt
        if time.time() >= deadline:
            # 超时也保存已拉取的数据（方便排查为何未匹配）
            _save_parsed_events(case_ws, sid, events)
            return None, None, events, attempt
        print(f"  埋点步骤: 第 {attempt} 次轮询未匹配到事件，等待 2s 后重试...")
        time.sleep(2)


def _extract_track_fields(event, layers):
    """从匹配的事件中提取关键字段值（顶层字段 + val_lab 各子层），供 AI 判定。"""
    extracted = {}
    for key in ("nm", "val_cid", "val_bid"):
        if event.get(key) is not None:
            extracted[key] = event[key]
    val_lab = event.get("val_lab")
    if isinstance(val_lab, dict) and val_lab:
        for lk, lv in val_lab.items():
            extracted[f"val_lab.{lk}"] = lv
    for layer_name, layer_dict in layers:
        if layer_name == "val_lab":
            continue
        if isinstance(layer_dict, dict):
            for lk, lv in layer_dict.items():
                extracted[f"{layer_name}.{lk}"] = lv
    return truncate_values(extracted)


def _take_screenshot(case_ws, ci, sid):
    """埋点步骤现场截图（归一到 frames/，失败返回 None）。"""
    try:
        ops = get_platform_ops()
        shot_name = f"{sid}.png" if sid else "track_step.png"
        if ci is not None:
            shot_name = f"case_{ci + 1:02d}_{shot_name}"
        out = frame_path(case_ws, shot_name)
        if ops.screenshot(out):
            return shot_name
    except Exception as e:
        soft_fail("device", "TRACK_STEP_SHOT_FAILED", e)
    return None


def _finalize_step(root_dir, case_ws, record, ci, sid, ok_val, action_type,
                   screenshot=None, fail_reason="", assertions=None):
    """统一收口：落盘记录 + 更新 flow-context + 记录 audit 事件。"""
    record.append(case_ws)
    fc_update_step(root_dir, sid, ok_val, action_type,
                   screenshot=screenshot, fail_reason=fail_reason,
                   assertions=assertions)
    append_event(root_dir, "step.completed", {
        "case_index": ci, "sid": sid, "result": ok_val, "kind": action_type,
    })


def execute_track_step(root_dir, case_ws, ctx, step_def, args):
    step_start = time.time()
    sid = step_def.get("sid", "")
    desc = step_def.get("desc", "")
    assertion = step_def.get("track_assert") or {}
    ci = ctx.get("current_case", {}).get("index")
    mis = resolve_mis(ctx.get("meta", {}).get("user_mis", ""))

    if not mis:
        raise FlowStateError("TRACK STEP ABORT: 无法确定 MIS 号")

    timeout_sec = assertion.get("wait_timeout_sec", 10)
    match_val = assertion.get("match", "")
    expected_fields = assertion.get("expected_fields") or {}
    # expected_fields 为可选字段，为空时只判断事件是否存在，不校验参数

    print(f"TRACK STEP [{sid}]: {desc}")
    print(f"  匹配: match={match_val} (按 val_bid → val_cid → nm 优先级自动查找) timeout={timeout_sec}s")
    if expected_fields:
        print(f"  字段校验: {len(expected_fields)} 个预期字段")

    event, source_item, events, attempts = _fetch_and_match_event(
        mis, assertion, timeout_sec, case_ws=case_ws, sid=sid,
    )

    # 无论成功失败，都补一张现场截图作为证据
    shot_name = _take_screenshot(case_ws, ci, sid)

    if not event:
        ok_val = 0
        recorded_events = [
            {"nm": e.get("nm", ""), "val_cid": e.get("val_cid", ""),
             "val_bid": e.get("val_bid", "")}
            for e in events[:20]
        ]
        record = StepRecord(
            sid=sid, src=SRC_STEP, type="track", desc=desc, ok=ok_val, status="FAIL",
            ms=int((time.time() - step_start) * 1000), kind="track",
            failure={"error": f"未匹配到埋点事件 (match={match_val})", "reason": "NO_MATCH",
                     "total_events": len(events), "attempts": attempts,
                     "recorded_events": recorded_events},
            extra={"matched": False},
        )
        record.shot(shot_name, label="埋点现场", kind=SHOT_STEP)
        _finalize_step(root_dir, case_ws, record, ci, sid, ok_val, "track", fail_reason="埋点事件未匹配")
        print(f"TRACK STEP [{sid}] ❌ FAIL | 未匹配到事件 (共轮询 {attempts} 次, 事件 {len(events)} 个)")
        if match_val and events:
            evt_names = [e.get("nm") or e.get("val_cid") or e.get("val_bid") for e in events[:10]]
            print(f"  💡 提示: 已捕获 {len(events)} 个埋点事件，但未匹配到 match={match_val}")
            print(f"     已捕获事件名: {evt_names}")
        elif not match_val:
            print(f"  💡 提示: track_assert.match 为空，常见原因：")
            print(f"     - track_assert 使用了 \"nm\" 字段，应改为 {{\"match\":\"事件名\"}}")
            print(f"     - track_assert 格式错误，正确示例: {{\"track_assert\": {{\"match\":\"c_hotel_createorder_unified\"}}}}")
        raise StepAssertionError(f"TRACK STEP [{sid}] 未匹配到埋点事件 (共 {attempts} 次轮询, 事件 {len(events)} 个)")

    event_nm = event.get("nm", "")
    print(f"  ✅ MATCHED | nm={event_nm}")

    layers = _collect_val_lab_layers(event)
    extracted_fields = _extract_track_fields(event, layers)

    evidence_path = _save_evidence(case_ws, sid, event, layers, extracted_fields, expected_fields=expected_fields)

    appmock_url = None
    try:
        if source_item is not None:
            url = _create_track_mock(source_item, event, mis)
            if url:
                appmock_url = url
                print(f"  AppMock: {url}")
    except Exception as e:
        soft_fail("infra", "TRACK_APPMOCK_ARCHIVE_FAILED", e)

    record = StepRecord(
        sid=sid, src=SRC_STEP, type="track", desc=desc, ok=1, status="PASS",
        ms=int((time.time() - step_start) * 1000), kind="track",
        fields=extracted_fields,
        expected_fields=expected_fields or None,
        extra={
            "matched": True,
            "event_nm": event_nm,
            "val_cid": event.get("val_cid"),
            "val_bid": event.get("val_bid"),
            "evidence_path": evidence_path,
        },
    )
    if appmock_url:
        record.extra["appmock_url"] = appmock_url
    record.shot(shot_name, label="埋点现场", kind=SHOT_STEP)

    assertions_data = None
    if expected_fields:
        assertions_data = {
            "track_fields": {
                "expected_fields": expected_fields,
                "evidence_path": evidence_path or "",
            }
        }

    _finalize_step(root_dir, case_ws, record, ci, sid, 1, "track",
                   screenshot=shot_name, fail_reason="", assertions=assertions_data)
    print(f"TRACK STEP [{sid}] ✅ PASS | nm={event_nm}")
    print(f"  📄 结构化证据: {evidence_path}")
    if expected_fields:
        print(f"  📋 待校验字段: {len(expected_fields)} 个（AI 将通过 hook 逐字段判定）")
    return 0
