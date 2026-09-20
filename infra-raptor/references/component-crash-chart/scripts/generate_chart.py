#!/usr/bin/env python3
"""
通用组件 Crash 趋势图（多平台）

支持三种模式：
  1. 小时级（默认）：单日分钟数据聚合为小时，支持多版本对比 + 发版时间线
  2. 7天趋势（--range 7d）：按天级粒度展示最近 7 天
  3. 版本对比（--versions）：在小时级图上叠加多条版本趋势线 + 自动标注首次出现时间

用法:
  # 小时级（默认）
  python3 generate_chart.py --date 2026-03-13 --group android:babel
  python3 generate_chart.py --date 2026-03-13 --group ios:horn

  # 7天趋势
  python3 generate_chart.py --date 2026-03-13 --group android:dsp --range 7d
  python3 generate_chart.py --date 2026-03-13 --group harmony:pike --range 7d

  # 多版本对比（自动叠加发版时间线）
  python3 generate_chart.py --date 2026-03-13 --group harmony:pike --versions 12.53.402,12.53.202
  python3 generate_chart.py --date 2026-03-13 --group android:dsp --versions auto  # 自动查 top5 版本

  # 自定义
  python3 generate_chart.py --date 2026-03-13 --project meituan --components "SAKHorn" --name "Horn-iOS" --range 7d
"""

import argparse
import json
import os
import re
import subprocess
import sys
from collections import defaultdict
from datetime import datetime, timedelta


# ── 前置依赖检查 ────────────────────────────────────────

def check_dependencies():
    """检查 raptorfe CLI 是否可用；不存在则自动安装"""
    r = subprocess.run("raptorfe --version", shell=True, capture_output=True, text=True)
    if r.returncode != 0:
        print("❌ raptorfe 未安装，正在安装...", file=sys.stderr)
        subprocess.run(
            "npm install -g @mtfe/raptorfe-cli --registry https://r.npm.sankuai.com/",
            shell=True, check=True
        )


import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np


# ── 平台 project 映射 ──────────────────────────────────
PLATFORMS = {
    # 美团
    "android": "android_platform_monitor",
    "ios": "meituan",
    "harmony": "meituan-harmony",
    # 点评
    "dp-android": "android-nova",
    "dp-ios": "nova",
    "dp-harmony": "harmony-nova",
    # 外卖
    "wm-android": "meituanwaimai",
    "wm-ios": "waimai_ios",
    "wm-harmony": "waimai-harmony",
}

# ── 预设组件组 ──────────────────────────────────────────
PRESET_GROUPS = {
    "android": {
        "dsp": {
            "display": "DSP (Android)",
            "components": {
                "dsp-business": "com.sankuai.meituan.mbc:dsp-business",
                "dsp-core": "com.sankuai.meituan.mbc:dsp-core",
            }
        },
        "babel": {
            "display": "Babel (Android)",
            "components": {
                "babel": "com.meituan.android.common.metricx:babel",
            }
        },
        "raptor": {
            "display": "Raptor (Android)",
            "components": {
                "basemonitor": "com.dianping.android.sdk:basemonitor",
            }
        },
        "pike": {
            "display": "Pike (Android)",
            "components": {
                "pike": "com.dianping.android.sdk:pike",
                "pike-knb-bridge": "com.dianping.android.sdk:pike-knb-bridge",
            }
        },
        "logan": {
            "display": "Logan (Android)",
            "components": {
                "networklog": "com.dianping.android.sdk:networklog",
                "clogan": "com.dianping.android.sdk:clogan",
            }
        },
        "common": {
            "display": "Common (Android)",
            "components": {
                "ui": "com.meituan.android.common:ui",
                "utils": "com.meituan.android.common:utils",
                "native": "com.meituan.android.common:native",
                "storage": "com.meituan.android.common:storage",
                "shortcut": "com.meituan.android.common:shortcut",
                "permission": "com.meituan.android.common:permission",
                "errorview": "com.meituan.android.common:errorview",
            }
        },
        "sniffer": {
            "display": "Sniffer (Android)",
            "components": {
                "sniffer": "com.meituan.android.common.metricx:sniffer",
            }
        },
        "horn": {
            "display": "Horn (Android)",
            "components": {
                "horn": "com.meituan.android.common:horn",
                "horn-interface": "com.meituan.android.common:horn-interface",
                "horn-core": "com.meituan.android.common:horn-core",
                "horn-uuid": "com.meituan.android.common:horn-uuid",
                "horn-sharkpush": "com.meituan.android.common:horn-sharkpush",
                "horn-raptor": "com.meituan.android.common:horn-raptor",
                "horn-monitor-1": "com.meituan.android.common.horn:horn-monitor",
                "horn-monitor-2": "com.meituan.android.common:horn-monitor",
                "horn-msi": "com.meituan.android.common:horn-msi",
            }
        },
    },
    "ios": {
        "horn": {
            "display": "SAKHorn (iOS)",
            "components": {
                "SAKHorn": "SAKHorn",
            }
        },
    },
    "harmony": {
        "horn": {
            "display": "Horn (HarmonyOS)",
            "components": {
                "horn": "horn",
            }
        },
        "pike": {
            "display": "Pike (HarmonyOS)",
            "components": {
                "@meituan/pike": "@meituan/pike",
            }
        },
    },
    "dp-android": {
        "dsp": {
            "display": "DSP (DP Android)",
            "components": {
                "dsp-business": "com.sankuai.meituan.mbc:dsp-business",
                "dsp-core": "com.sankuai.meituan.mbc:dsp-core",
            }
        },
        "babel": {
            "display": "Babel (DP Android)",
            "components": {
                "babel": "com.meituan.android.common.metricx:babel",
            }
        },
        "raptor": {
            "display": "Raptor (DP Android)",
            "components": {
                "basemonitor": "com.dianping.android.sdk:basemonitor",
            }
        },
        "pike": {
            "display": "Pike (DP Android)",
            "components": {
                "pike": "com.dianping.android.sdk:pike",
                "pike-knb-bridge": "com.dianping.android.sdk:pike-knb-bridge",
            }
        },
        "logan": {
            "display": "Logan (DP Android)",
            "components": {
                "networklog": "com.dianping.android.sdk:networklog",
                "clogan": "com.dianping.android.sdk:clogan",
            }
        },
        "horn": {
            "display": "Horn (DP Android)",
            "components": {
                "horn": "com.meituan.android.common:horn",
                "horn-interface": "com.meituan.android.common:horn-interface",
                "horn-core": "com.meituan.android.common:horn-core",
                "horn-uuid": "com.meituan.android.common:horn-uuid",
                "horn-sharkpush": "com.meituan.android.common:horn-sharkpush",
                "horn-raptor": "com.meituan.android.common:horn-raptor",
                "horn-monitor-1": "com.meituan.android.common.horn:horn-monitor",
                "horn-monitor-2": "com.meituan.android.common:horn-monitor",
                "horn-msi": "com.meituan.android.common:horn-msi",
            }
        },
        "sniffer": {
            "display": "Sniffer (DP Android)",
            "components": {
                "sniffer": "com.meituan.android.common.metricx:sniffer",
            }
        },
    },
    "dp-ios": {
        "horn": {
            "display": "SAKHorn (DP iOS)",
            "components": {
                "SAKHorn": "SAKHorn",
            }
        },
    },
    "dp-harmony": {
        "pike": {
            "display": "Pike (DP HarmonyOS)",
            "components": {
                "@meituan/pike": "@meituan/pike",
            }
        },
        "horn": {
            "display": "Horn (DP HarmonyOS)",
            "components": {
                "horn": "horn",
            }
        },
    },
    "wm-android": {
        "babel": {
            "display": "Babel (WM Android)",
            "components": {
                "babel": "com.meituan.android.common.metricx:babel",
            }
        },
    },
    "wm-ios": {
        "babel": {
            "display": "Babel (WM iOS)",
            "components": {
                "babel": "babel",
            }
        },
        "horn": {
            "display": "SAKHorn (WM iOS)",
            "components": {
                "SAKHorn": "SAKHorn",
            }
        },
    },
    "wm-harmony": {
        "babel": {
            "display": "Babel (WM HarmonyOS)",
            "components": {
                "babel": "babel",
            }
        },
        "pike": {
            "display": "Pike (WM HarmonyOS)",
            "components": {
                "@meituan/pike": "@meituan/pike",
            }
        },
        "core": {
            "display": "Core (WM HarmonyOS)",
            "components": {
                "@machpro/core": "@machpro/core",
                "@mach/core": "@mach/core",
            }
        },
    },
}

COLORS = ['#ef4444', '#f59e0b', '#3b82f6', '#10b981', '#8b5cf6', '#ec4899', '#06b6d4']


# ── Data helpers ────────────────────────────────────────
def _parse_data_items(text):
    """解析 CLI/MCP 返回数据，兼容多种格式，支持截断兜底。
    返回 [(dt_str, count), ...]，dt_str 格式为 'YYYY-MM-DD HH:MM:SS'
    """
    items = []

    # raptorfe CLI 新格式：{"ok":true,"data":[{"dt":"2026-04-07 10:00","value":123}]}
    # dt 格式可能为 "YYYY-MM-DD HH:MM" 或 "YYYY-MM-DD HH:MM:SS"
    def _parse_raptorfe_cli(src):
        _items = []
        try:
            obj = json.loads(src) if isinstance(src, str) else src
            if not obj.get("ok"):
                return _items
            for item in obj.get("data", []) or []:
                dt = str(item.get("dt", ""))
                value = item.get("value", 0)
                if not dt or value is None:
                    continue
                # 补全秒
                if len(dt) == 16:  # "YYYY-MM-DD HH:MM"
                    dt = dt + ":00"
                _items.append((dt, int(float(value))))
        except Exception:
            pass
        return _items

    # 优先尝试 raptorfe CLI 格式
    try:
        cli_items = _parse_raptorfe_cli(text.strip())
        if cli_items:
            return cli_items
    except Exception:
        pass

    # crash_time_data 格式：{"success":true,"data":"{\"data\":[{\"x\":\"20260319\",\"y\":114}]}"}
    # x 格式: YYYYMMDD (日级) 或 YYYYMMDDHH (小时级) 或 YYYYMMDDHHmm (分钟级)
    def _parse_crash_xy(src):
        _items = []
        try:
            outer = json.loads(src) if isinstance(src, str) else src
            data_str = outer.get("data", "")
            if isinstance(data_str, str) and data_str:
                inner = json.loads(data_str)
            elif isinstance(data_str, dict):
                inner = data_str
            else:
                return _items
            for item in inner.get("data", []) or []:
                x = str(item.get("x", ""))
                y = item.get("y", 0)
                if not x or y is None:
                    continue
                # x 格式: 
                #   "20260325"         → 日级 (8位纯数字)
                #   "2026032508"       → 小时级 (10位纯数字)
                #   "202603250802"     → 分钟级 (12位纯数字)
                #   "20260325 08:02"   → 分钟级 (含空格, crash_time_data minute)
                #   "2026032508"       → 小时级
                import re as _re
                # 先处理含空格格式："YYYYMMDD HH:MM"（分钟级）或 "YYYYMMDD HH"（小时级）
                m_space_min = _re.match(r'(\d{8}) (\d{2}):(\d{2})', x)
                m_space_hour = _re.match(r'(\d{8}) (\d{2})$', x)
                if m_space_min:
                    dt_str = f"{x[0:4]}-{x[4:6]}-{x[6:8]} {m_space_min.group(2)}:{m_space_min.group(3)}:00"
                elif m_space_hour:
                    dt_str = f"{x[0:4]}-{x[4:6]}-{x[6:8]} {m_space_hour.group(2)}:00:00"
                elif len(x) == 8:
                    dt_str = f"{x[:4]}-{x[4:6]}-{x[6:8]} 00:00:00"
                elif len(x) == 10:
                    dt_str = f"{x[:4]}-{x[4:6]}-{x[6:8]} {x[8:10]}:00:00"
                elif len(x) == 12:
                    dt_str = f"{x[:4]}-{x[4:6]}-{x[6:8]} {x[8:10]}:{x[10:12]}:00"
                else:
                    continue
                _items.append((dt_str, int(float(y))))
        except Exception:
            pass
        return _items

    # 先尝试整段解析（mcporter --output json 输出多行格式化 JSON）
    try:
        _parsed = _parse_crash_xy(text.strip())
        if _parsed:
            return _parsed
    except Exception:
        pass
    # 分段拼接时：按 {"success" 分割成多个 JSON 块，逐块解析
    import re as _re2
    for chunk in _re2.split(r'(?=\{\s*"success")', text):
        chunk = chunk.strip()
        if not chunk:
            continue
        _parsed = _parse_crash_xy(chunk)
        items.extend(_parsed)
    if items:
        return items

    # 新版：从整段文本中提取所有 JSON 对象（{"success":true,"message":"..."} 格式）
    for m in re.finditer(r'\{"success"\s*:\s*true\s*,\s*"message"\s*:\s*"((?:[^"\\]|\\.)*)"\}', text):
        try:
            inner = json.loads(m.group(1).replace('\\"', '"').encode().decode('unicode_escape').encode('latin-1').decode('utf-8'))
            for method_block in inner.get("data", []):
                for item in method_block.get("dataInfoList", []):
                    try:
                        items.append((item["dt"], int(float(item["value"]))))
                    except (KeyError, ValueError):
                        pass
        except Exception:
            pass

    # 新版 JSON：直接 json.loads 整段（mcporter --output json 模式）
    if not items:
        for block in text.split('\n'):
            block = block.strip()
            if not block:
                continue
            try:
                outer = json.loads(block)
                msg = outer.get("message", "")
                if isinstance(msg, str):
                    inner = json.loads(msg)
                else:
                    inner = msg
                for method_block in inner.get("data", []):
                    for item in method_block.get("dataInfoList", []):
                        try:
                            items.append((item["dt"], int(float(item["value"]))))
                        except (KeyError, ValueError):
                            pass
            except Exception:
                pass

    # 新版截断兜底：正则从残缺 JSON 中抠数据
    if not items:
        for m in re.finditer(
            r'\\"dt\\"[:\s]*\\"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\\"[^}]*\\"value\\"[:\s]*([\d.]+)',
            text
        ):
            try:
                items.append((m.group(1), int(float(m.group(2)))))
            except ValueError:
                pass

    # 旧版 YAML 格式兜底
    if not items:
        for m in re.finditer(
            r'dt: "(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})".*?value: (\d+)',
            text, re.DOTALL
        ):
            items.append((m.group(1), int(m.group(2))))

    return items


def mcporter_query(metrics_name, start, end, filters, granularity="ONE_MINUTE", timeout=120, distinct=False, data_type="crash"):
    """查询 Crash/ANR 数据，使用 raptorfe CLI（内置鉴权）。
    granularity: ONE_MINUTE->minute, ONE_HOUR->hour, DAY->day
    filters 格式: [("project", val), ("default_component", val), ("appVersion", val), ...]
    """
    import json as _json
    from datetime import datetime as _dt, timedelta as _td

    fmt = "%Y-%m-%d %H:%M:%S"

    # granularity 映射
    granularity_map = {"ONE_MINUTE": "minute", "ONE_HOUR": "hour", "DAY": "day"}
    interval = granularity_map.get(granularity, "minute")

    # 从 filters 中提取各字段
    filter_dict = {}
    for f in filters:
        if isinstance(f, (list, tuple)) and len(f) == 2:
            filter_dict[f[0]] = f[1]
        elif isinstance(f, dict):
            filter_dict[f.get("tagName", "")] = (f.get("tagValues", [""])[0] if isinstance(f.get("tagValues"), list) else f.get("tagValues", ""))

    project = filter_dict.get("project", "android_platform_monitor")
    component = filter_dict.get("default_component", "")
    version = filter_dict.get("appVersion", "")

    def _run_query_with_filter(s, e):
        cmd_parts = [
            "raptorfe crash timeseries get",
            f"--project {project}",
            f"--type {data_type}",
            f'--start "{s}"',
            f'--end "{e}"',
            f"--interval {interval}",
        ]
        if version:
            cmd_parts.append(f'--filter "appVersion:{version}"')
        if component:
            cmd_parts.append(f'--filter "default_component:{component}"')
        cmd = " ".join(cmd_parts)
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout + 10)
        return r.stdout

    # 分钟级分段查询（每1小时一段，防超时）
    if granularity == "ONE_MINUTE":
        try:
            t_start = _dt.strptime(start, fmt)
            t_end = _dt.strptime(end, fmt)
            if t_end <= t_start:
                t_end += _td(days=1)
        except ValueError:
            t_start = None

        if t_start is not None:
            all_output = ""
            cur = t_start
            while cur < t_end:
                nxt = min(cur + _td(hours=1), t_end)
                all_output += _run_query_with_filter(cur.strftime(fmt), nxt.strftime(fmt)) + "\n"
                cur = nxt
            return all_output

    return _run_query_with_filter(start, end)

def aggregate_hourly(text):
    hourly = defaultdict(int)
    for dt_str, val in _parse_data_items(text):
        try:
            hour = int(dt_str[11:13])
            hourly[hour] += val
        except (ValueError, IndexError):
            pass
    return dict(sorted(hourly.items()))


def aggregate_minute(text):
    """解析分钟级数据，返回 {HH:MM: count}"""
    minute_data = defaultdict(int)
    for dt_str, val in _parse_data_items(text):
        try:
            hhmm = dt_str[11:16]
            minute_data[hhmm] += val
        except (ValueError, IndexError):
            pass
    return dict(sorted(minute_data.items()))


def parse_daily(text):
    """解析日级数据，返回 {date_str: count}，兼容新版 JSON 和旧版 YAML 格式"""
    daily = {}

    # 新版 JSON 格式：复用 _parse_data_items 解析所有数据点，取 00:00:00 的点
    items = _parse_data_items(text)
    for dt_str, val in items:
        if dt_str.endswith(" 00:00:00"):
            date = dt_str[:10]
            daily[date] = daily.get(date, 0) + val

    # 旧版 YAML 格式兜底
    if not daily:
        for m in re.finditer(
            r'dt: "(\d{4}-\d{2}-\d{2}) 00:00:00".*?value: (\d+)',
            text, re.DOTALL
        ):
            daily[m.group(1)] = int(m.group(2))

    return daily


def parse_distinct_daily(text):
    """从含 distinctCount 的响应中解析日级去重数，返回 {date_str: count}"""
    distinct = {}
    # 用 _parse_response_blocks 兼容解析（复用已有的 JSON 解析路径）
    # 直接搜索 "distinctCount" + dt + value
    for m in re.finditer(
        r'"method"\s*:\s*"distinctCount".*?"dataInfoList"\s*:\s*\[(.*?)\]',
        text, re.DOTALL
    ):
        for item_m in re.finditer(
            r'"dt"\s*:\s*"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})".*?"value"\s*:\s*([\d.]+)',
            m.group(1), re.DOTALL
        ):
            dt_str = item_m.group(1)
            val = float(item_m.group(2))
            if dt_str.endswith(" 00:00:00"):
                date = dt_str[:10]
                distinct[date] = distinct.get(date, 0) + int(val)
    # 兜底：解析 message 字段里的转义 JSON
    if not distinct:
        for msg_m in re.finditer(r'"message"\s*:\s*"((?:[^"\\]|\\.)*)"', text):
            try:
                inner = json.loads('"' + msg_m.group(1) + '"')
                data = json.loads(inner)
                for block in (data.get("data") or []):
                    if block.get("method") == "distinctCount":
                        for item in (block.get("dataInfoList") or []):
                            dt_str = item.get("dt", "")
                            val = item.get("value", 0)
                            if dt_str and dt_str.endswith(" 00:00:00"):
                                date = dt_str[:10]
                                distinct[date] = distinct.get(date, 0) + int(val or 0)
            except Exception:
                continue
    return distinct


def query_top_versions(project, component, date, next_day, top_n=5):
    """查询某组件在指定日期范围内的 top N 版本。
    用 raptorfe crash field-suggestions 获取版本枚举（往前扩展7天提高覆盖度），
    再逐版本用 timeseries get 查数量排序。
    """
    import json as _json
    from datetime import datetime as _dt, timedelta as _td
    # 往前扩展采样范围（取 date 前7天），提高版本覆盖度
    try:
        _end = _dt.strptime(next_day, "%Y-%m-%d")
        _start = _dt.strptime(date, "%Y-%m-%d") - _td(days=6)
        sample_start = _start.strftime("%Y-%m-%d 00:00:00")
        sample_end = _end.strftime("%Y-%m-%d 00:00:00")
    except Exception:
        sample_start = f"{date} 00:00:00"
        sample_end = f"{next_day} 00:00:00"

    # Step1: 用 field-suggestions 获取版本枚举（替代 crash_log_detail_post_json 采样）
    filter_arg = f'--filter "default_component:{component}"' if component else ""
    cmd = (
        f'raptorfe crash field-suggestions get'
        f' --project {project} --type crash --field appVersion'
        f' --start "{sample_start}" --end "{sample_end}"'
        f' {filter_arg}'
    )
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=40)
    versions_seen = []
    try:
        obj = _json.loads(r.stdout.strip())
        if obj.get("ok"):
            data = obj.get("data", []) or []
            if isinstance(data, list):
                versions_seen = [str(v) for v in data if v]
            elif isinstance(data, dict):
                # 部分版本返回 {values: [...]}
                versions_seen = [str(v) for v in data.get("values", []) if v]
    except Exception as e:
        print(f"  [warn] query_top_versions step1 error: {e}, stdout={r.stdout[:200]}", file=sys.stderr)

    if not versions_seen:
        print("  [warn] query_top_versions: no versions found, skip release timeline", file=sys.stderr)
        return []

    # Step2: 逐版本查 crash 数量（在原始 date~next_day 范围内），排序取 top_n
    ver_counts = []
    for ver in versions_seen[:top_n * 2]:
        raw = mcporter_query(
            "perf.crash", f"{date} 00:00:00", f"{next_day} 00:00:00",
            [("project", project), ("default_component", component), ("appVersion", ver)],
            granularity="DAY", timeout=30
        )
        daily = parse_daily(raw)
        cnt = sum(daily.values())
        ver_counts.append((ver, cnt))
    ver_counts.sort(key=lambda x: -x[1])
    return [v[0] for v in ver_counts[:top_n]]

def query_version_first_day(project, component, versions, start_date, end_date):
    """
    查询各版本在 7 天范围内首次出现的日期（日级粒度）。
    返回 {version: date_str}，只包含首次出现的版本。
    """
    # 用 getPerfMetricTagTrend 按 appVersion 下钻，DAY 粒度，最多返回 top5
    # 因为接口只返回 top5，这里对已知版本逐一按版本 filter 查首天
    first_days = {}
    end_next = (datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
    for ver in versions:
        raw = mcporter_query(
            "perf.crash", f"{start_date} 00:00:00", f"{end_next} 00:00:00",
            [("project", project), ("default_component", component), ("appVersion", ver)],
            granularity="DAY", timeout=60
        )
        daily = parse_daily(raw)
        # 找最早有 crash 的日期
        for d in sorted(daily.keys()):
            if daily[d] > 0:
                first_days[ver] = d
                break
    return first_days


def query_version_hourly(project, component, version, date, next_day):
    """查询单个版本的小时级 crash 数据"""
    raw = mcporter_query(
        "perf.crash", f"{date} 00:00:00", f"{next_day} 00:00:00",
        [("project", project), ("default_component", component), ("appVersion", version)]
    )
    return aggregate_hourly(raw)


def detect_version_first_hour(hourly_data):
    """返回版本首次出现的小时（crash > 0 的最小小时），None 表示无数据"""
    for h in sorted(hourly_data.keys()):
        if hourly_data[h] > 0:
            return h
    return None


def list_groups():
    lines = []
    for platform, groups in PRESET_GROUPS.items():
        for group_name, info in groups.items():
            comps = ", ".join(info["components"].values())
            lines.append(f"  {platform}:{group_name:<12} → {info['display']:<25} [{comps}]")
    return "\n".join(lines)


def resolve_group(args):
    """解析 --group 或 --project+--components，返回 (display_name, components, project)"""
    if args.group:
        parts = args.group.split(":", 1)
        if len(parts) != 2:
            print(f"ERROR: --group format: platform:group. Got: {args.group}", file=sys.stderr)
            sys.exit(1)
        platform, group_name = parts
        if platform not in PRESET_GROUPS:
            print(f"ERROR: Unknown platform: {platform}. Available: {', '.join(PRESET_GROUPS.keys())}", file=sys.stderr)
            sys.exit(1)
        if group_name not in PRESET_GROUPS[platform]:
            avail = ", ".join(PRESET_GROUPS[platform].keys())
            print(f"ERROR: Unknown group '{group_name}' for {platform}. Available: {avail}", file=sys.stderr)
            sys.exit(1)
        group_info = PRESET_GROUPS[platform][group_name]
        return group_info["display"], group_info["components"], PLATFORMS[platform]
    else:
        display_name = args.name or "Custom"
        comps = [c.strip() for c in args.components.split(",")]
        components = {}
        for c in comps:
            if "=" in c:
                k, v = c.split("=", 1)
                components[k.strip()] = v.strip()
            else:
                components[c.split(":")[-1]] = c
        return display_name, components, args.project


# ── 分钟级图表 ──────────────────────────────────────────
def draw_minute(date, display_name, components, project, output):
    _chart_type = getattr(__import__('builtins'), '_chart_data_type', 'crash'); type_label = 'ANR' if _chart_type == 'anr' else 'Crash'
    next_day = (datetime.strptime(date, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
    yesterday = (datetime.strptime(date, "%Y-%m-%d") - timedelta(days=1)).strftime("%Y-%m-%d")
    yesterday_next = date
    print(f"Querying {display_name} crash (minute) for {date} (project={project})...", file=sys.stderr)

    crash_data = {}
    for label, comp_name in components.items():
        print(f"  crash/{label} minute (project={project}, component={comp_name})...", file=sys.stderr)
        raw = mcporter_query("perf.crash", f"{date} 00:00:00", f"{next_day} 00:00:00",
                             [("project", project), ("default_component", comp_name)], timeout=120)
        crash_data[label] = aggregate_minute(raw)

    # 查昨天对比数据
    compare_data = {}
    print(f"  [compare] querying {yesterday} (minute)...", file=sys.stderr)
    cday_data = {}
    for label, comp_name in components.items():
        raw = mcporter_query("perf.crash", f"{yesterday} 00:00:00", f"{yesterday_next} 00:00:00",
                             [("project", project), ("default_component", comp_name)], timeout=120)
        cday_data[label] = aggregate_minute(raw)
    compare_data[yesterday] = cday_data

    # 合并所有分钟点（含对比日，避免 x 轴截断）
    all_minutes = set()
    for d in crash_data.values():
        all_minutes.update(d.keys())
    for cday in compare_data.values():
        for d in cday.values():
            all_minutes.update(d.keys())
    if not all_minutes:
        print("ERROR: No crash data returned.", file=sys.stderr)
        sys.exit(1)

    minutes = sorted(all_minutes)
    n = len(minutes)
    x = np.arange(n)

    num_comp = len(components)
    comp_vals = {l: [crash_data.get(l, {}).get(m, 0) for m in minutes] for l in components}
    comp_sums = {l: sum(v) for l, v in comp_vals.items()}
    total_crash = [sum(comp_vals[l][i] for l in components) for i in range(n)]
    sum_crash = sum(total_crash)

    # x 轴标签：每 30 分钟显示一次，其余空白
    x_labels = [m if m.endswith(":00") or m.endswith(":30") else "" for m in minutes]

    print("Generating minute chart...", file=sys.stderr)
    compare_colors = ['#94a3b8', '#f97316', '#22d3ee', '#a3e635']

    if num_comp == 1:
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(20, 9), gridspec_kw={'height_ratios': [3, 2]})
        fig.suptitle(f'{display_name} {type_label} (Minute) — {date} | Total: {sum_crash}',
                     fontsize=15, fontweight='bold', y=0.99)
        label = list(components.keys())[0]
        vals = comp_vals[label]
        color = COLORS[0]
        avg_val = sum_crash / n if n > 0 else 0

        ax1.fill_between(x, vals, alpha=0.12, color=color)
        ax1.plot(x, vals, '-', color=color, linewidth=1.2, label=f'{date}  Total: {sum_crash}')
        # 昨天对比线
        for ci, (cdate, cday_data) in enumerate(compare_data.items()):
            cc = compare_colors[ci % len(compare_colors)]
            cvals = [cday_data.get(label, {}).get(m, 0) for m in minutes]
            ax1.plot(x, cvals, '-', color=cc, linewidth=1.0, alpha=0.7,
                     label=f'{cdate} (ref)  Total: {sum(cvals)}')
        ax1.set_ylabel('Crash Count', fontsize=11)
        ax1.legend(fontsize=10)
        ax1.set_title(f'{display_name} {type_label} per Minute vs {yesterday}', fontsize=12, pad=8)
        ax1.grid(True, alpha=0.3)
        ax1.set_xticks(x[::1]); ax1.set_xticklabels(x_labels, rotation=45, ha='right', fontsize=8)

        ax2.bar(x, vals, color=color, alpha=0.6, width=1.0, label=f'{date}')
        for ci, (cdate, cday_data) in enumerate(compare_data.items()):
            cc = compare_colors[ci % len(compare_colors)]
            cvals = [cday_data.get(label, {}).get(m, 0) for m in minutes]
            ax2.plot(x, cvals, '-', color=cc, linewidth=1.0, alpha=0.75,
                     label=f'{cdate} (ref)')
        ax2.axhline(y=avg_val, color='#ef4444', linestyle='--', linewidth=1.2, alpha=0.7,
                    label=f'Avg({date}): {avg_val:.2f}/min')
        ax2.set_ylabel('Crash Count', fontsize=11)
        ax2.set_title(f'Bar | Avg: {avg_val:.2f}/min', fontsize=12, pad=8)
        ax2.grid(True, alpha=0.3, axis='y')
        ax2.set_xticks(x[::1]); ax2.set_xticklabels(x_labels, rotation=45, ha='right', fontsize=8)
        ax2.legend(fontsize=10)
    else:
        fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(20, 13),
                                             gridspec_kw={'height_ratios': [3, 2, 2]})
        fig.suptitle(f'{display_name} {type_label} (Minute) — {date} | Total: {sum_crash}',
                     fontsize=15, fontweight='bold', y=0.995)
        avg_val = sum_crash / n if n > 0 else 0

        for idx, label in enumerate(components):
            color = COLORS[idx % len(COLORS)]
            ax1.plot(x, comp_vals[label], '-', color=color, linewidth=1.2,
                     label=f'{label}  Total: {comp_sums[label]}', alpha=0.85)
        # 昨天合计对比线
        for ci, (cdate, cday_data) in enumerate(compare_data.items()):
            cc = compare_colors[ci % len(compare_colors)]
            ctotal = [sum(cday_data.get(l, {}).get(m, 0) for l in components) for m in minutes]
            ax1.plot(x, ctotal, '-', color=cc, linewidth=1.0, alpha=0.7,
                     label=f'{cdate} Total (ref): {sum(ctotal)}')
        ax1.set_ylabel('Crash Count', fontsize=11)
        ax1.legend(fontsize=9, loc='upper left')
        ax1.set_title(f'{display_name} {type_label} by Component (Minute) vs {yesterday}', fontsize=12, pad=8)
        ax1.grid(True, alpha=0.3)
        ax1.set_xticks(x); ax1.set_xticklabels(x_labels, rotation=45, ha='right', fontsize=8)

        w = 0.8 / num_comp
        for idx, label in enumerate(components):
            color = COLORS[idx % len(COLORS)]
            offset = (idx - num_comp / 2 + 0.5) * w
            ax2.bar(x + offset, comp_vals[label], w, color=color, alpha=0.7,
                    label=f'{label}')
        ax2.set_ylabel('Crash Count', fontsize=11)
        ax2.legend(fontsize=9)
        ax2.set_title(f'Bar by Component', fontsize=12, pad=8)
        ax2.grid(True, alpha=0.3, axis='y')
        ax2.set_xticks(x); ax2.set_xticklabels(x_labels, rotation=45, ha='right', fontsize=8)

        ax3.fill_between(x, total_crash, alpha=0.12, color='#6366f1')
        ax3.plot(x, total_crash, '-', color='#6366f1', linewidth=1.5, label=f'{date} Total: {sum_crash}')
        for ci, (cdate, cday_data) in enumerate(compare_data.items()):
            cc = compare_colors[ci % len(compare_colors)]
            ctotal = [sum(cday_data.get(l, {}).get(m, 0) for l in components) for m in minutes]
            ax3.plot(x, ctotal, '-', color=cc, linewidth=1.0, alpha=0.75,
                     label=f'{cdate} Total (ref): {sum(ctotal)}')
        ax3.axhline(y=avg_val, color='#ef4444', linestyle='--', linewidth=1.2, alpha=0.7,
                    label=f'Avg: {avg_val:.2f}/min')
        ax3.set_ylabel('Total Crash', fontsize=11)
        ax3.set_title(f'Total {type_label} per Minute | Avg: {avg_val:.2f}/min', fontsize=12, pad=8)
        ax3.grid(True, alpha=0.3)
        ax3.set_xticks(x); ax3.set_xticklabels(x_labels, rotation=45, ha='right', fontsize=8)
        ax3.legend(fontsize=10)

    plt.tight_layout(rect=[0, 0, 1, 0.97])
    plt.savefig(output, dpi=150, bbox_inches='tight', facecolor='white')

    print(f"Chart saved: {output}")
    print(f"\n=== Summary ===")
    print(f"Date: {date}")
    print(f"Platform/Group: {display_name} (project={project})")
    for label in components:
        print(f"  {label}: {comp_sums[label]}")
    print(f"Total Crash: {sum_crash}")
    print(f"Output: {output}")

    # 分钟级分析结论
    comp_lines = "\n".join(f"  - {l}: {comp_sums[l]}次" for l in components)
    print(f"\n=== 分析结论 ===")
    print(f"**{display_name} {type_label} 分钟级（{date}）**\n")
    print(f"**概况：**")
    print(f"- 今日截至当前：{sum_crash}次")
    print(comp_lines)
    print(f"\n*详见图表（分钟级精度，适合排查短时突刺）*")


# ── 小时级图表 ──────────────────────────────────────────
def draw_hourly(date, display_name, components, project, output, compare_dates=None):
    """
    compare_dates: list of YYYY-MM-DD strings to overlay as reference lines (同比/环比).
    默认带昨天对比线，除非 compare_dates=[] 显式传空。
    """
    _chart_type = getattr(__import__('builtins'), '_chart_data_type', 'crash'); type_label = 'ANR' if _chart_type == 'anr' else 'Crash'
    if compare_dates is None:
        yesterday = (datetime.strptime(date, "%Y-%m-%d") - timedelta(days=1)).strftime("%Y-%m-%d")
        compare_dates = [yesterday]
    next_day = (datetime.strptime(date, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")

    print(f"Querying {display_name} crash for {date} (project={project})...", file=sys.stderr)
    crash_data = {}
    for label, comp_name in components.items():
        print(f"  crash/{label} (project={project}, component={comp_name})...", file=sys.stderr)
        raw = mcporter_query("perf.crash", f"{date} 00:00:00", f"{next_day} 00:00:00",
                             [("project", project), ("default_component", comp_name)])
        crash_data[label] = aggregate_hourly(raw)

    # 查对比日数据
    compare_data = {}          # date_str -> {label -> {hour: count}}
    compare_day_totals = {}    # date_str -> int (分钟级累加，不去重，与 Raptor 崩溃量口径一致)
    compare_distinct_totals = {}  # 不再使用，影响用户数数据不准已禁用
    for cdate in compare_dates:
        cnext = (datetime.strptime(cdate, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
        print(f"  [compare] querying {cdate}...", file=sys.stderr)
        cday_data = {}
        cday_total = 0
        for label, comp_name in components.items():
            # 对比日用小时级查询，避免分钟级分段累加口径偏差
            raw = mcporter_query("perf.crash", f"{cdate} 00:00:00", f"{cnext} 00:00:00",
                                 [("project", project), ("default_component", comp_name)],
                                 granularity="ONE_HOUR")
            cday_data[label] = aggregate_hourly(raw)
            cday_total += sum(cday_data[label].values())
        compare_data[cdate] = cday_data
        compare_day_totals[cdate] = cday_total

    all_hours = set()
    for d in crash_data.values():
        all_hours.update(d.keys())
    # 把对比日数据也纳入 x 轴范围，避免对比线被截断
    for cday_data in compare_data.values():
        for d in cday_data.values():
            all_hours.update(d.keys())
    if not all_hours:
        print("ERROR: No crash data returned.", file=sys.stderr)
        sys.exit(1)

    max_hour = max(all_hours)
    hours_range = range(max_hour + 1)
    hours = [f"{h:02d}:00" for h in hours_range]
    n = len(hours)
    x = np.arange(n)

    comp_vals = {l: [crash_data.get(l, {}).get(h, 0) for h in hours_range] for l in components}
    comp_sums = {l: sum(v) for l, v in comp_vals.items()}
    total_crash = [sum(comp_vals[l][i] for l in components) for i in range(n)]
    sum_crash = sum(total_crash)

    # 崩溃量 = 分钟级累加（不去重，与 Raptor 崩溃量口径一致）
    # 影响用户数 = DAY 粒度 distinctCount（deviceId 去重，与 Raptor 影响用户数口径一致）
    # 注意：DAY 粒度 totalCount 不等于 Raptor 崩溃量（存在去重），不使用
    sum_crash_display = sum_crash  # 分钟级累加，不去重
    day_distinct_total = 0  # 不展示影响用户数（数据不准，已禁用）
    print(f"  [total] crash={sum_crash_display} (minute-sum, no dedup)", file=sys.stderr)

    print("Generating hourly chart...", file=sys.stderr)
    num_comp = len(components)

    distinct_label = f" | Affected Users: {day_distinct_total}" if day_distinct_total > 0 else ""
    if num_comp == 1:
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(15, 9), gridspec_kw={'height_ratios': [3, 2]})
        fig.suptitle(f'{display_name} {type_label} Hourly — {date} | Total: {sum_crash_display}{distinct_label}',
                     fontsize=16, fontweight='bold', y=0.99)
        label = list(components.keys())[0]
        vals = comp_vals[label]
        color = COLORS[0]

        ax1.fill_between(x, vals, alpha=0.15, color=color)
        ax1.plot(x, vals, 'o-', color=color, linewidth=2.5, markersize=6,
                 label=f'{date}  Total: {comp_sums[label]}')

        # 同比对比线
        compare_colors = ['#94a3b8', '#f97316', '#22d3ee', '#a3e635']
        for ci, (cdate, cday_data) in enumerate(compare_data.items()):
            cc = compare_colors[ci % len(compare_colors)]
            cvals = [cday_data.get(label, {}).get(h, 0) for h in hours_range]
            ctotal = compare_day_totals.get(cdate, sum(cvals))
            ax1.plot(x, cvals, 's--', color=cc, linewidth=1.8, markersize=4, alpha=0.8,
                     label=f'{cdate} (ref)  Total: {ctotal}')


        ax1.set_ylabel('Crash Count', fontsize=12)
        ax1.legend(fontsize=10, loc='upper left')
        compare_label = f" vs {', '.join(compare_data.keys())}" if compare_data else ""
        ax1.set_title(f'{display_name} {type_label} (Line){compare_label}', fontsize=13, pad=8)
        ax1.grid(True, alpha=0.3)
        ax1.set_xticks(x); ax1.set_xticklabels(hours, rotation=45, ha='right', fontsize=9)
        for i in range(n):
            if vals[i] > 0:
                ax1.annotate(str(vals[i]), (i, vals[i]), textcoords="offset points",
                             xytext=(0, 8), ha='center', fontsize=8, fontweight='bold', color=color)

        avg_val = sum_crash_display / n if n > 0 else 0
        bar_colors = ['#ef4444' if v >= max(5, avg_val * 2) else '#8b5cf6' for v in vals]
        ax2.bar(x, vals, color=bar_colors, alpha=0.75, width=0.6, label=f'{date}')
        # 对比日的折线叠在柱状图上
        for ci, (cdate, cday_data) in enumerate(compare_data.items()):
            cc = compare_colors[ci % len(compare_colors)]
            cvals = [cday_data.get(label, {}).get(h, 0) for h in hours_range]
            ax2.plot(x, cvals, 's--', color=cc, linewidth=1.8, markersize=4, alpha=0.85,
                     label=f'{cdate} (ref)')
        ax2.axhline(y=avg_val, color='#6366f1', linestyle='--', linewidth=1.5, alpha=0.7,
                    label=f'Avg({date}): {avg_val:.1f}')
        ax2.set_ylabel('Crash Count', fontsize=12)
        ax2.set_title(f'{display_name} {type_label} (Bar) | Avg: {avg_val:.1f}/h{compare_label}', fontsize=13, pad=8)
        ax2.grid(True, alpha=0.3, axis='y')
        ax2.set_xticks(x); ax2.set_xticklabels(hours, rotation=45, ha='right', fontsize=9)
        ax2.legend(fontsize=10)
    else:
        fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(15, 13),
                                             gridspec_kw={'height_ratios': [3, 2, 2]})
        fig.suptitle(f'{display_name} {type_label} Hourly — {date} | Total: {sum_crash_display}{distinct_label}',
                     fontsize=16, fontweight='bold', y=0.995)

        compare_label = f" vs {', '.join(compare_data.keys())}" if compare_data else ""
        compare_colors = ['#94a3b8', '#f97316', '#22d3ee', '#a3e635']

        for idx, label in enumerate(components):
            color = COLORS[idx % len(COLORS)]
            ax1.plot(x, comp_vals[label], 'o-', color=color, linewidth=2, markersize=5,
                     label=f'{date} {label}  Total: {comp_sums[label]}')
        # 同比折线（各组件合计）
        for ci, (cdate, cday_data) in enumerate(compare_data.items()):
            cc = compare_colors[ci % len(compare_colors)]
            ctotal = [sum(cday_data.get(l, {}).get(h, 0) for l in components) for h in hours_range]
            cday_total_label = compare_day_totals.get(cdate, sum(ctotal))
            ax1.plot(x, ctotal, 's--', color=cc, linewidth=1.8, markersize=4, alpha=0.8,
                     label=f'{cdate} Total (ref): {cday_total_label}')
        ax1.set_ylabel('Crash Count', fontsize=11)
        ax1.legend(fontsize=9, loc='upper left')
        ax1.set_title(f'{display_name} {type_label} by Component (Line){compare_label}', fontsize=12, pad=8)
        ax1.grid(True, alpha=0.3)
        ax1.set_xticks(x); ax1.set_xticklabels(hours, rotation=45, ha='right', fontsize=9)

        w = 0.8 / num_comp
        for idx, label in enumerate(components):
            color = COLORS[idx % len(COLORS)]
            offset = (idx - num_comp / 2 + 0.5) * w
            ax2.bar(x + offset, comp_vals[label], w, color=color, alpha=0.75,
                    label=f'{label}  Total: {comp_sums[label]}')
            for i in range(n):
                if comp_vals[label][i] > 0:
                    ax2.text(i + offset, comp_vals[label][i] + 0.15, str(comp_vals[label][i]),
                             ha='center', va='bottom', fontsize=7, fontweight='bold', color=color)
        ax2.set_ylabel('Crash Count', fontsize=11)
        ax2.legend(fontsize=9, loc='upper left')
        ax2.set_title(f'{display_name} {type_label} by Component (Bar)', fontsize=12, pad=8)
        ax2.grid(True, alpha=0.3, axis='y')
        ax2.set_xticks(x); ax2.set_xticklabels(hours, rotation=45, ha='right', fontsize=9)

        avg_val = sum_crash_display / n if n > 0 else 0
        ax3.fill_between(x, total_crash, alpha=0.15, color='#6366f1')
        ax3.plot(x, total_crash, 'o-', color='#6366f1', linewidth=2.5, markersize=5,
                 label=f'{date} Total: {sum_crash_display}')
        ax3.axhline(y=avg_val, color='#ef4444', linestyle='--', linewidth=1.5, alpha=0.7,
                    label=f'Avg: {avg_val:.1f}')
        # 同比合计线
        for ci, (cdate, cday_data) in enumerate(compare_data.items()):
            cc = compare_colors[ci % len(compare_colors)]
            ctotal = [sum(cday_data.get(l, {}).get(h, 0) for l in components) for h in hours_range]
            cday_total_label = compare_day_totals.get(cdate, sum(ctotal))
            ax3.plot(x, ctotal, 's--', color=cc, linewidth=1.8, markersize=4, alpha=0.85,
                     label=f'{cdate} Total (ref): {cday_total_label}')
        ax3.set_ylabel('Total Crash', fontsize=11)
        ax3.set_title(f'{display_name} Total {type_label} | Avg: {avg_val:.1f}/h{compare_label}', fontsize=12, pad=8)
        ax3.grid(True, alpha=0.3)
        ax3.set_xticks(x); ax3.set_xticklabels(hours, rotation=45, ha='right', fontsize=9)
        ax3.legend(fontsize=10)
        for i in range(n):
            if total_crash[i] > 0:
                ax3.annotate(str(total_crash[i]), (i, total_crash[i]),
                             textcoords="offset points", xytext=(0, 8),
                             ha='center', fontsize=8, fontweight='bold', color='#6366f1')

    plt.tight_layout(rect=[0, 0, 1, 0.97])
    plt.savefig(output, dpi=150, bbox_inches='tight', facecolor='white')

    print(f"Chart saved: {output}")
    print(f"\n=== Summary ===")
    print(f"Date: {date}")
    print(f"Platform/Group: {display_name} (project={project})")
    for label in components:
        print(f"  {label}: {comp_sums[label]}")
    print(f"Total Crash: {sum_crash_display}")
    if day_distinct_total > 0:
        print(f"Affected Users (uuid distinct): {day_distinct_total}")
    if compare_day_totals:
        print(f"Compare (DAY):")
        for cdate, ctotal in compare_day_totals.items():
            print(f"  {cdate}: {ctotal}")
    print(f"Output: {output}")

    # 标准分析结论输出
    _data_type_str = getattr(__import__("builtins"), "_chart_data_type", "crash")
    hourly_flat = [sum(comp_vals[l][i] for l in components) for i in range(n)]
    analysis = build_notify_message(
        display_name, date, comp_sums, sum_crash_display,
        compare_totals=compare_day_totals if compare_day_totals else None,
        mode_label="小时级",
        hourly_data=hourly_flat,
        distinct_users=day_distinct_total if day_distinct_total > 0 else None,
        compare_distinct=compare_distinct_totals if compare_distinct_totals else None,
        compare_hourly=compare_data if compare_data else None,
        data_type=_data_type_str
    )
    print(f"\n=== 分析结论 ===")
    print(analysis)


# ── 发版时间线辅助（7天图用）────────────────────────────
VERSION_TIMELINE_COLORS = ['#dc2626', '#d97706', '#7c3aed', '#065f46', '#1e40af', '#9d174d']

def _draw_version_timeline_7d(ax_line, ax_bar, dates, version_first_day):
    """
    在7天折线图和柱状图上绘制版本发版时间线竖线。
    version_first_day: {version: date_str}
    dates: list of 'YYYY-MM-DD' (7 items, index = x position)
    """
    if not version_first_day:
        return
    date_to_x = {d: i for i, d in enumerate(dates)}
    for rank, (ver, fday) in enumerate(sorted(version_first_day.items(), key=lambda kv: kv[1])):
        xi = date_to_x.get(fday)
        if xi is None:
            continue
        color = VERSION_TIMELINE_COLORS[rank % len(VERSION_TIMELINE_COLORS)]
        for ax in (ax_line, ax_bar):
            ax.axvline(x=xi, color=color, linestyle='--', linewidth=1.8, alpha=0.65,
                       zorder=5)
        # 只在折线图标注版本号（避免柱状图太挤）
        ymin, ymax = ax_line.get_ylim()
        label_y = ymin + (ymax - ymin) * (0.05 + 0.14 * (rank % 4))
        ax_line.text(xi + 0.08, label_y, f'v{ver}',
                     fontsize=8, color=color, va='bottom', ha='left',
                     bbox=dict(boxstyle='round,pad=0.2', facecolor='white',
                               alpha=0.8, edgecolor=color))


# ── N天趋势图表 ────────────────────────────────────────
def draw_7day(end_date, display_name, components, project, output):
    """Backward-compat wrapper."""
    draw_nday(end_date, display_name, components, project, output, days=7)


def draw_nday(end_date, display_name, components, project, output, days=7):
    _chart_type = getattr(__import__('builtins'), '_chart_data_type', 'crash'); type_label = 'ANR' if _chart_type == 'anr' else 'Crash'
    end_dt = datetime.strptime(end_date, "%Y-%m-%d")
    start_dt = end_dt - timedelta(days=days - 1)
    start_str = start_dt.strftime("%Y-%m-%d")
    end_next = (end_dt + timedelta(days=1)).strftime("%Y-%m-%d")

    dates = [(start_dt + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(days)]
    date_labels = [(start_dt + timedelta(days=i)).strftime("%m-%d") for i in range(days)]
    n = days
    x = np.arange(n)

    print(f"Querying {display_name} crash {days}-day trend {start_str} ~ {end_date} (project={project})...", file=sys.stderr)

    # 每个组件查 N 天日级数据，今天用分钟级聚合（更实时）
    today_str = datetime.now().strftime("%Y-%m-%d")
    comp_daily = {}
    for label, comp_name in components.items():
        print(f"  crash/{label} {days}-day (project={project}, component={comp_name})...", file=sys.stderr)
        raw = mcporter_query("perf.crash", f"{start_str} 00:00:00", f"{end_next} 00:00:00",
                             [("project", project), ("default_component", comp_name)],
                             granularity="DAY", timeout=120)
        daily = parse_daily(raw)
        # 今天用分钟级实时数据替换（延迟更小）
        if end_date == today_str:
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            raw_min = mcporter_query("perf.crash", f"{end_date} 00:00:00", now_str,
                                     [("project", project), ("default_component", comp_name)])
            items_min = _parse_data_items(raw_min)
            today_total = sum(v for _, v in items_min)
            if today_total > 0:
                daily[end_date] = today_total
        comp_daily[label] = daily

    # 查 top5 版本 + 各版本首现日（取第一个组件代表）
    first_comp_name = list(components.values())[0]
    print(f"  Querying top5 versions for release timeline...", file=sys.stderr)
    top_versions = query_top_versions(project, first_comp_name, start_str, end_next, top_n=5)
    version_first_day = {}
    if top_versions:
        version_first_day = query_version_first_day(project, first_comp_name, top_versions, start_str, end_date)
        print(f"  Version first-day: {version_first_day}", file=sys.stderr)

    comp_vals = {l: [comp_daily.get(l, {}).get(d, 0) for d in dates] for l in components}
    comp_sums = {l: sum(v) for l, v in comp_vals.items()}
    total_daily = [sum(comp_vals[l][i] for l in components) for i in range(n)]
    sum_crash = sum(total_daily)
    avg_val = sum_crash / n if n > 0 else 0

    print("Generating 7-day chart...", file=sys.stderr)
    num_comp = len(components)

    if num_comp == 1:
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 9), gridspec_kw={'height_ratios': [3, 2]})
        fig.suptitle(f'{display_name} {type_label} {days}-Day Trend — {start_str} ~ {end_date} | Total: {sum_crash}',
                     fontsize=15, fontweight='bold', y=0.99)

        label = list(components.keys())[0]
        vals = comp_vals[label]
        color = COLORS[0]

        ax1.fill_between(x, vals, alpha=0.15, color=color)
        ax1.plot(x, vals, 'o-', color=color, linewidth=2.5, markersize=8,
                 label=f'{label}  Total: {comp_sums[label]}')
        ax1.set_ylabel('Daily Crash Count', fontsize=12)
        ax1.legend(fontsize=11, loc='upper left')
        ax1.set_title(f'{display_name} Daily {type_label} (Line)', fontsize=13, pad=8)
        ax1.grid(True, alpha=0.3)
        ax1.set_xticks(x); ax1.set_xticklabels(date_labels, fontsize=9 if n > 10 else 11, rotation=45 if n > 10 else 0, ha="right" if n > 10 else "center")
        for i in range(n):
            ax1.annotate(str(vals[i]), (i, vals[i]), textcoords="offset points",
                         xytext=(0, 10), ha='center', fontsize=10, fontweight='bold', color=color)

        # 发版时间线
        _draw_version_timeline_7d(ax1, ax2, dates, version_first_day)

        bar_colors = ['#ef4444' if v >= max(10, avg_val * 1.5) else '#8b5cf6' for v in vals]
        ax2.bar(x, vals, color=bar_colors, alpha=0.75, width=0.5)
        ax2.axhline(y=avg_val, color='#6366f1', linestyle='--', linewidth=1.5, alpha=0.7,
                    label=f'Avg: {avg_val:.0f}/day')
        ax2.set_ylabel('Daily Crash Count', fontsize=12)
        ax2.set_title(f'{display_name} Daily {type_label} (Bar) | Avg: {avg_val:.0f}/day  [dashed=release]', fontsize=13, pad=8)
        ax2.grid(True, alpha=0.3, axis='y')
        ax2.set_xticks(x); ax2.set_xticklabels(date_labels, fontsize=9 if n > 10 else 11, rotation=45 if n > 10 else 0, ha="right" if n > 10 else "center")
        ax2.legend(fontsize=10)

    else:
        fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(14, 13),
                                             gridspec_kw={'height_ratios': [3, 2, 2]})
        fig.suptitle(f'{display_name} {type_label} {days}-Day Trend — {start_str} ~ {end_date} | Total: {sum_crash}',
                     fontsize=15, fontweight='bold', y=0.995)

        for idx, label in enumerate(components):
            color = COLORS[idx % len(COLORS)]
            ax1.plot(x, comp_vals[label], 'o-', color=color, linewidth=2, markersize=7,
                     label=f'{label}  Total: {comp_sums[label]}')
        ax1.set_ylabel('Daily Crash', fontsize=11)
        ax1.legend(fontsize=10, loc='upper left')
        ax1.set_title(f'{display_name} {type_label} by Component (7-Day)', fontsize=12, pad=8)
        ax1.grid(True, alpha=0.3)
        ax1.set_xticks(x); ax1.set_xticklabels(date_labels, fontsize=9 if n > 10 else 11, rotation=45 if n > 10 else 0, ha="right" if n > 10 else "center")

        w = 0.8 / num_comp
        for idx, label in enumerate(components):
            color = COLORS[idx % len(COLORS)]
            offset = (idx - num_comp / 2 + 0.5) * w
            ax2.bar(x + offset, comp_vals[label], w, color=color, alpha=0.75,
                    label=f'{label}  Total: {comp_sums[label]}')
            for i in range(n):
                if comp_vals[label][i] > 0:
                    ax2.text(i + offset, comp_vals[label][i] + 0.5, str(comp_vals[label][i]),
                             ha='center', va='bottom', fontsize=8, fontweight='bold', color=color)
        ax2.set_ylabel('Daily Crash', fontsize=11)
        ax2.legend(fontsize=9, loc='upper left')
        ax2.set_title(f'{display_name} Daily {type_label} by Component (Bar)', fontsize=12, pad=8)
        ax2.grid(True, alpha=0.3, axis='y')
        ax2.set_xticks(x); ax2.set_xticklabels(date_labels, fontsize=9 if n > 10 else 11, rotation=45 if n > 10 else 0, ha="right" if n > 10 else "center")

        ax3.fill_between(x, total_daily, alpha=0.15, color='#6366f1')
        ax3.plot(x, total_daily, 'o-', color='#6366f1', linewidth=2.5, markersize=7,
                 label=f'Total  {sum_crash}')
        ax3.axhline(y=avg_val, color='#ef4444', linestyle='--', linewidth=1.5, alpha=0.7,
                    label=f'Avg: {avg_val:.0f}/day')
        ax3.set_ylabel('Total Daily Crash', fontsize=11)
        ax3.set_title(f'{display_name} Total {type_label} | Avg: {avg_val:.0f}/day  [dashed=release]', fontsize=12, pad=8)
        ax3.grid(True, alpha=0.3)
        ax3.set_xticks(x); ax3.set_xticklabels(date_labels, fontsize=9 if n > 10 else 11, rotation=45 if n > 10 else 0, ha="right" if n > 10 else "center")
        ax3.legend(fontsize=10)
        for i in range(n):
            ax3.annotate(str(total_daily[i]), (i, total_daily[i]),
                         textcoords="offset points", xytext=(0, 10),
                         ha='center', fontsize=9, fontweight='bold', color='#6366f1')

        # 发版时间线（多组件模式，ax1=折线 ax2=柱状 ax3=合计折线）
        _draw_version_timeline_7d(ax1, ax2, dates, version_first_day)
        # ax3（合计折线）也加发版时间线
        if version_first_day:
            date_to_x = {d: i for i, d in enumerate(dates)}
            for rank, (ver, fday) in enumerate(sorted(version_first_day.items(), key=lambda kv: kv[1])):
                xi = date_to_x.get(fday)
                if xi is not None:
                    color = VERSION_TIMELINE_COLORS[rank % len(VERSION_TIMELINE_COLORS)]
                    ax3.axvline(x=xi, color=color, linestyle='--', linewidth=1.8, alpha=0.65, zorder=5)

    plt.tight_layout(rect=[0, 0, 1, 0.97])
    plt.savefig(output, dpi=150, bbox_inches='tight', facecolor='white')

    print(f"Chart saved: {output}")
    print(f"\n=== Summary ===")
    print(f"Range: {start_str} ~ {end_date} ({days} days)")
    print(f"Platform/Group: {display_name} (project={project})")
    for label in components:
        vals = comp_vals[label]
        print(f"  {label}: {comp_sums[label]} ({' / '.join(str(v) for v in vals)})")
    print(f"Total Crash: {sum_crash}")
    print(f"Avg: {avg_val:.0f}/day")
    if version_first_day:
        print(f"Release timeline:")
        for ver, fday in sorted(version_first_day.items(), key=lambda kv: kv[1]):
            print(f"  v{ver}: first seen {fday}")
    print(f"Output: {output}")

    # 7天趋势分析结论
    all_daily = [sum(comp_vals[l][i] for l in components) for i in range(days)]
    peak_val = max(all_daily) if all_daily else 0
    peak_day = dates[all_daily.index(peak_val)] if all_daily else ""
    today_val = all_daily[-1] if all_daily else 0
    trend = "↓ 下行" if all_daily[-1] < all_daily[0] else ("↑ 上行" if all_daily[-1] > all_daily[0] else "→ 平稳")
    comp_lines = "\n".join(f"  - {l}: {comp_sums[l]}次" for l in components)
    print(f"\n=== 分析结论 ===")
    print(f"**{display_name} {type_label} {days}天趋势（{start_str} ~ {end_date}）**\n")
    print(f"**概况：**")
    print(f"- {days}天总计：{sum_crash}次，日均 {avg_val:.0f}次/天")
    print(comp_lines)
    print(f"\n**趋势：**")
    print(f"- 峰值：{peak_day}（{peak_val}次），今日（{end_date}）：{today_val}次，整体 {trend}")
    if version_first_day:
        ver_str = "、".join(f"v{ver}（{fday}）" for ver, fday in sorted(version_first_day.items(), key=lambda kv: kv[1]))
        print(f"- 版本发布：{ver_str}")
    print(f"\n*详见图表*")


# ── 多版本对比图表 ────────────────────────────────────────
def draw_version_compare(date, display_name, components, project, versions_arg, output):
    """
    多版本对比：对每个组件，按版本分别拉小时级 crash 数据，多线叠加绘制。
    同时在图上用竖线标注各版本首次出现时间（作为发版时间线近似）。
    """
    _chart_type = getattr(__import__('builtins'), '_chart_data_type', 'crash'); type_label = 'ANR' if _chart_type == 'anr' else 'Crash'
    next_day = (datetime.strptime(date, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")

    # 只取第一个组件做版本对比（多组件时取合并总量）
    comp_labels = list(components.keys())
    comp_names = list(components.values())

    # 解析版本列表
    if versions_arg.strip().lower() == "auto":
        print(f"Auto-detecting top5 versions for {display_name} on {date}...", file=sys.stderr)
        versions = query_top_versions(project, comp_names[0], date, next_day, top_n=5)
        if not versions:
            print("No version data found, falling back to hourly chart.", file=sys.stderr)
            draw_hourly(date, display_name, components, project, output)
            return
        print(f"Top versions: {versions}", file=sys.stderr)
    else:
        versions = [v.strip() for v in versions_arg.split(",") if v.strip()]

    # 查每个版本的小时级数据（所有组件合并）
    print(f"Querying {len(versions)} versions × {len(comp_names)} components...", file=sys.stderr)
    version_data = {}   # version -> {hour: count}
    for ver in versions:
        combined = defaultdict(int)
        for comp_name in comp_names:
            print(f"  version={ver}, component={comp_name}", file=sys.stderr)
            hourly = query_version_hourly(project, comp_name, ver, date, next_day)
            for h, v in hourly.items():
                combined[h] += v
        version_data[ver] = dict(combined)

    # 也查一下全版本合计
    all_combined = defaultdict(int)
    for ver_d in version_data.values():
        for h, v in ver_d.items():
            all_combined[h] += v

    all_hours = set(all_combined.keys())
    for ver_d in version_data.values():
        all_hours.update(ver_d.keys())
    if not all_hours:
        print("ERROR: No data for any version.", file=sys.stderr)
        sys.exit(1)

    max_hour = max(all_hours)
    hours_range = list(range(max_hour + 1))
    hours = [f"{h:02d}:00" for h in hours_range]
    n = len(hours)
    x = np.arange(n)

    total_all = sum(all_combined.values())
    ver_totals = {ver: sum(version_data[ver].values()) for ver in versions}

    # 发版时间线：每个版本首次出现的小时
    version_first_hour = {}
    for ver in versions:
        fh = detect_version_first_hour(version_data[ver])
        if fh is not None:
            version_first_hour[ver] = fh

    print("Generating version-compare chart...", file=sys.stderr)

    # 布局：上方折线（多版本叠加）+ 下方柱状（全版本合计）
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(16, 10), gridspec_kw={'height_ratios': [3, 2]})
    fig.suptitle(
        f'{display_name} Crash — Version Compare — {date} | Total(all ver): {total_all}',
        fontsize=15, fontweight='bold', y=0.99
    )

    # ── 上图：多版本折线 ──
    for idx, ver in enumerate(versions):
        color = COLORS[idx % len(COLORS)]
        vals = [version_data[ver].get(h, 0) for h in hours_range]
        ax1.plot(x, vals, 'o-', color=color, linewidth=2, markersize=5,
                 label=f'v{ver}  Total: {ver_totals[ver]}', alpha=0.85)
        # 在折线末端注数字（只标峰值）
        peak_i = int(np.argmax(vals))
        if vals[peak_i] > 0:
            ax1.annotate(str(vals[peak_i]), (peak_i, vals[peak_i]),
                         textcoords="offset points", xytext=(0, 7),
                         ha='center', fontsize=8, fontweight='bold', color=color)

    # 发版时间线竖线（在所有数据绘完后再画，使 ylim 稳定）
    ax1.autoscale_view()
    ymin, ymax = ax1.get_ylim()
    label_y_step = (ymax - ymin) * 0.12
    for rank, (ver, fh) in enumerate(sorted(version_first_hour.items(), key=lambda kv: kv[1])):
        color = COLORS[versions.index(ver) % len(COLORS)]
        xi = fh
        if xi < n:
            ax1.axvline(x=xi, color=color, linestyle='--', linewidth=1.5, alpha=0.6)
            label_y = ymin + label_y_step * (rank % 4 + 0.5)
            ax1.text(xi + 0.18, label_y,
                     f'v{ver}\nFirst: {fh:02d}:xx', fontsize=7, color=color,
                     va='bottom', ha='left', rotation=0,
                     bbox=dict(boxstyle='round,pad=0.2', facecolor='white', alpha=0.75, edgecolor=color))

    ax1.set_ylabel('Crash Count', fontsize=12)
    ax1.legend(fontsize=10, loc='upper right', ncol=min(len(versions), 3))
    ax1.set_title(f'{display_name} {type_label} by Version (Line)  [dashed line = first appearance]', fontsize=12, pad=8)
    ax1.grid(True, alpha=0.3)
    ax1.set_xticks(x)
    ax1.set_xticklabels(hours, rotation=45, ha='right', fontsize=9)

    # ── 下图：全版本合计柱状 + 各版本堆叠 ──
    # 堆叠柱状图，每个版本一层
    bottom = np.zeros(n)
    for idx, ver in enumerate(versions):
        color = COLORS[idx % len(COLORS)]
        vals = np.array([version_data[ver].get(h, 0) for h in hours_range])
        ax2.bar(x, vals, bottom=bottom, color=color, alpha=0.7, width=0.6,
                label=f'v{ver}')
        bottom += vals

    # 平均线
    total_per_hour = [all_combined.get(h, 0) for h in hours_range]
    avg_val = sum(total_per_hour) / n if n > 0 else 0
    ax2.axhline(y=avg_val, color='#1f2937', linestyle='--', linewidth=1.5, alpha=0.6,
                label=f'Avg: {avg_val:.1f}/h')

    # 发版时间线（下图同步）
    for ver, fh in version_first_hour.items():
        color = COLORS[versions.index(ver) % len(COLORS)]
        if fh < n:
            ax2.axvline(x=fh, color=color, linestyle='--', linewidth=1.2, alpha=0.5)

    ax2.set_ylabel('Crash Count (Stacked)', fontsize=12)
    ax2.set_title(f'Version Stacked Bar | Avg: {avg_val:.1f}/h (all versions)', fontsize=12, pad=8)
    ax2.legend(fontsize=9, loc='upper right', ncol=min(len(versions), 4))
    ax2.grid(True, alpha=0.3, axis='y')
    ax2.set_xticks(x)
    ax2.set_xticklabels(hours, rotation=45, ha='right', fontsize=9)

    plt.tight_layout(rect=[0, 0, 1, 0.97])
    plt.savefig(output, dpi=150, bbox_inches='tight', facecolor='white')

    print(f"Chart saved: {output}")
    print(f"\n=== Version Compare Summary ===")
    print(f"Date: {date}")
    print(f"Platform/Group: {display_name} (project={project})")
    print(f"Versions: {', '.join(versions)}")
    for ver in versions:
        fh_str = f"首现 {version_first_hour[ver]:02d}:xx" if ver in version_first_hour else "无数据"
        print(f"  v{ver}: total={ver_totals[ver]}, {fh_str}")
    print(f"Total (all versions): {total_all}")
    print(f"Output: {output}")

    # 版本对比分析结论
    sorted_vers = sorted(ver_totals.items(), key=lambda kv: kv[1], reverse=True)
    worst_ver, worst_val = sorted_vers[0] if sorted_vers else ("?", 0)
    best_ver, best_val = sorted_vers[-1] if sorted_vers else ("?", 0)
    ver_lines = "\n".join(
        f"  - v{ver}: {cnt}次（{'首现 ' + str(version_first_hour[ver]) + ':xx' if ver in version_first_hour else '无发版数据'}）"
        for ver, cnt in sorted_vers
    )
    print(f"\n=== 分析结论 ===")
    print(f"**{display_name} {type_label} 版本对比（{date}）**\n")
    print(f"**版本分布：**")
    print(ver_lines)
    print(f"\n**结论：**")
    print(f"- crash 最多：v{worst_ver}（{worst_val}次），最少：v{best_ver}（{best_val}次）")
    print(f"- 各版本合计：{total_all}次")
    print(f"\n*详见图表*")


# ── 修复效果通知辅助 ──────────────────────────────────────
def notify_daxiang(misid, message_text, img_url=None):
    """
    推送大象消息。
    优先尝试 openclaw CLI；失败时写 pending 文件，等待 Agent heartbeat 发送。
    Pending 文件路径：~/.openclaw/skills/component-crash-chart/pending_notify.json
    """
    import subprocess as _sp, json as _json, pathlib as _pl, datetime as _dt
    full_msg = message_text
    if img_url:
        full_msg += f"\n\n![图片]({img_url})"

    # 先尝试 CLI 发送
    cmd = ["openclaw", "message", "send",
           "--channel", "daxiang",
           "--target", f"user:{misid}",
           "--message", full_msg]
    r = _sp.run(cmd, capture_output=True, text=True, timeout=30)
    if r.returncode == 0:
        print(f"[notify] Message sent to {misid}", file=sys.stderr)
        return

    # CLI 失败 → 写 pending 文件，由 Agent heartbeat 发送
    print(f"[notify] CLI failed, writing pending file for Agent to deliver", file=sys.stderr)
    pending_path = _pl.Path(__file__).parent.parent / "pending_notify.json"
    pending = {
        "misid": misid,
        "message": full_msg,
        "img_url": img_url,
        "created_at": _dt.datetime.now().isoformat(),
    }
    with open(pending_path, "w") as pf:
        _json.dump(pending, pf, ensure_ascii=False, indent=2)
    print(f"[notify] Pending written to {pending_path}", file=sys.stderr)


def upload_to_s3(file_path):
    """
    调用 s3plus-upload 上传图片，返回 URL（失败返回 None）。
    """
    import subprocess as _sp
    object_name = os.path.basename(file_path)
    upload_script_abs = "/root/.openclaw/skills/s3plus-upload/scripts/upload_to_s3plus.py"
    cmd = ["python3", upload_script_abs,
           "--file", file_path,
           "--env", "prod-corp",
           "--object-name", object_name]
    r = _sp.run(cmd, capture_output=True, text=True, timeout=60)
    if r.returncode != 0:
        print(f"[upload] WARN: upload failed: {r.stderr.strip()}", file=sys.stderr)
        return None
    url = r.stdout.strip().splitlines()[-1].strip()
    print(f"[upload] Uploaded: {url}", file=sys.stderr)
    return url


def build_notify_message(display_name, date, comp_sums, sum_crash,
                          compare_totals=None, mode_label="小时级",
                          hourly_data=None, distinct_users=None, compare_distinct=None,
                          compare_hourly=None, data_type="crash"):
    # compare_hourly: dict {date_str -> {label -> {hour: count}}} 对比日的小时级原始数据
    """
    构建大象通知消息文本（无图部分）。
    compare_totals: dict {date_str -> int} 对比日崩溃量（DAY粒度，不去重）
    hourly_data: list of int, 长度=当前小时数，用于波动分析和全天估算
    distinct_users: int or None，今日影响用户数（deviceId去重，对应 Raptor 影响用户数）
    compare_distinct: dict {date_str -> int} or None，对比日影响用户数（deviceId去重）
    """
    _tlabel = "ANR" if data_type == "anr" else "Crash"
    lines = [f"**{display_name} {_tlabel} {mode_label}（{date}）**", ""]
    lines.append("**概况：**")

    comp_lines = [f"{label}: {cnt}" for label, cnt in comp_sums.items()]
    lines.append(f"- 今日截至当前：{sum_crash}（{'，'.join(comp_lines)}）")

    # 全天估算（仅小时级模式）
    if hourly_data and mode_label == "小时级":
        elapsed_hours = len([v for v in hourly_data if v is not None])
        if 0 < elapsed_hours < 24:
            estimated = int(sum_crash / elapsed_hours * 24)
            lines.append(f"- 按当前进度估算全天约 **{estimated} 次**（已过 {elapsed_hours}h）")

    if compare_totals:
        first_cdate = list(compare_totals.keys())[0]
        yest_total = compare_totals[first_cdate]
        if yest_total > 0:
            elapsed_hours = len([v for v in (hourly_data or []) if v is not None]) if hourly_data else 0
            # 判断当天是否为今天且数据不完整（用日期+当前小时判断，Asia/Shanghai）
            import datetime as _datetime_mod
            _cst = _datetime_mod.timezone(_datetime_mod.timedelta(hours=8))
            _now_cst = _datetime_mod.datetime.now(_cst)
            _today = _now_cst.strftime("%Y-%m-%d")
            _current_hour = _now_cst.hour  # 0-23 CST
            is_partial = hourly_data and mode_label == "小时级" and date == _today and _current_hour < 23
            elapsed_hours = _current_hour + 1  # 已过小时数（CST，含当前小时）
            if is_partial:
                # 当天数据不完整：用昨天同时段（0~elapsed_hours）对比，而非全天
                yest_same_period = 0
                if compare_hourly:
                    for cdate_key, cday_labels in compare_hourly.items():
                        for label_data in cday_labels.values():
                            yest_same_period += sum(
                                v for h, v in label_data.items()
                                if int(h) < elapsed_hours
                            )
                estimated = int(sum_crash / elapsed_hours * 24)
                if yest_same_period > 0:
                    diff_sp = sum_crash - yest_same_period
                    pct_sp = diff_sp / yest_same_period * 100
                    arrow_sp = "↑" if diff_sp > 0 else "↓"
                    trend_sp = "环比恶化 🔴" if pct_sp > 10 else ("环比改善 🟢" if pct_sp < -10 else "基本持平 🟡")
                    lines.append(f"- 今日 0~{elapsed_hours}h：**{sum_crash}**，昨日同时段：**{yest_same_period}**，{arrow_sp}{abs(diff_sp)}（{pct_sp:+.1f}%）→ **{trend_sp}**（全天估算约 {estimated}）")
                else:
                    lines.append(f"- 今日截至 {elapsed_hours}h：**{sum_crash}**，全天估算约 {estimated}（昨日同时段数据不可用）")
            else:
                # 当天数据完整：正常环比
                diff = sum_crash - yest_total
                pct = diff / yest_total * 100
                arrow = "↑" if diff > 0 else "↓"
                trend = "环比恶化 🔴" if pct > 10 else ("环比改善 🟢" if pct < -10 else "基本持平 🟡")
                lines.append(f"- 今天全天：{sum_crash}，昨天（{first_cdate}）：{yest_total}，{arrow}{abs(diff)}（{pct:+.1f}%）→ **{trend}**")
        else:
            lines.append(f"- 崩溃量：昨天（{first_cdate}）：0，今日 {sum_crash} → **新增 🔴**")

    # 影响用户数及昨日对比
    if distinct_users is not None and distinct_users > 0:
        if compare_distinct:
            first_cdate = list(compare_distinct.keys())[0]
            yest_distinct = compare_distinct.get(first_cdate, 0)
            if yest_distinct > 0:
                diff_d = distinct_users - yest_distinct
                pct_d = diff_d / yest_distinct * 100
                arrow_d = "↑" if diff_d > 0 else "↓"
                lines.append(f"- Affected Users：昨天（{first_cdate}）{yest_distinct}，今天 **{distinct_users}**，{arrow_d}{abs(diff_d)}（{pct_d:+.1f}%）")
            else:
                lines.append(f"- Affected Users (uuid distinct): **{distinct_users}**")
        else:
            lines.append(f"- Affected Users (uuid distinct): **{distinct_users}**")

    # 波动分析
    if hourly_data and mode_label == "小时级":
        nonzero = [(i, v) for i, v in enumerate(hourly_data) if v and v > 0]
        if nonzero:
            avg = sum_crash / max(len([v for v in hourly_data if v is not None]), 1)
            spike_hours = [(h, v) for h, v in nonzero if v >= max(3, avg * 2)]
            if spike_hours:
                spike_str = "，".join([f"{h:02d}点({v}次)" for h, v in spike_hours])
                lines.append(f"- ⚠️ 集中爆发时段：{spike_str}")
            else:
                lines.append(f"- 各时段分布较平稳，无明显集中爆发")

    lines.append("")
    lines.append("*详见图表*")
    return "\n".join(lines)


# ── Main ────────────────────────────────────────────────
def main():
    check_dependencies()
    parser = argparse.ArgumentParser(
        description="Component Crash Chart (multi-platform, hourly or 7-day)",
        epilog=f"Available preset groups:\n{list_groups()}",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--date", required=True, help="YYYY-MM-DD (end date for 7d range)")
    parser.add_argument("--group", help="Preset: platform:group (e.g. android:dsp, ios:horn)")
    parser.add_argument("--project", help="Custom project value")
    parser.add_argument("--components", help="Custom component names, comma-separated")
    parser.add_argument("--name", help="Display name for custom query")
    parser.add_argument("--range", dest="time_range", help="Time range: '7d' for 7-day trend (default: hourly)")
    parser.add_argument("--versions",
                        help="Version compare mode: comma-separated versions (e.g. 12.53.402,12.53.202) or 'auto' for top5")
    parser.add_argument("--compare",
                        help="YoY/DoD compare date(s), comma-separated YYYY-MM-DD, or 'yesterday'/'auto' (default: yesterday). "
                             "Used with hourly mode to overlay reference trend lines.")
    parser.add_argument("--compare-days", type=int, default=0,
                        help="How many previous days to overlay (e.g. --compare-days 3 = yesterday + day-2 + day-3). "
                             "Overrides --compare when set.")
    parser.add_argument("--output", help="Output PNG path")
    parser.add_argument("--minute", action="store_true", help="Minute-level chart (no hourly aggregation)")
    parser.add_argument("--type", default="crash", choices=["crash", "anr"], help="数据类型: crash（默认）或 anr")
    parser.add_argument("--list", action="store_true", help="List all preset groups")
    parser.add_argument("--notify", metavar="MISID",
                        help="After generating chart: upload to S3 + send Daxiang message "
                             "(e.g. --notify nieyunlong). For cron fix-effect monitoring.")
    args = parser.parse_args()

    if args.list:
        print("Available preset groups:")
        print(list_groups())
        return

    if not args.group and not (args.project and args.components):
        parser.error("Must specify --group (e.g. android:dsp) or --project + --components")

    display_name, components, project = resolve_group(args)
    date = args.date
    safe_name = display_name.lower().replace(' ', '-').replace('(', '').replace(')', '')
    data_type = getattr(args, 'type', 'crash')
    type_suffix = '-anr' if data_type == 'anr' else ''
    import builtins as _bt; _bt._chart_data_type = data_type

    if args.minute:
        output = args.output or f"{safe_name}{type_suffix}-minute-{date}.png"
        draw_minute(date, display_name, components, project, output)
    elif args.versions:
        output = args.output or f"{safe_name}{type_suffix}-versions-{date}.png"
        draw_version_compare(date, display_name, components, project, args.versions, output)
    elif args.time_range and re.match(r'(\d+)d', args.time_range):
        days = int(re.match(r'(\d+)d', args.time_range).group(1))
        output = args.output or f"{safe_name}{type_suffix}-{days}d-{date}.png"
        draw_nday(date, display_name, components, project, output, days=days)
    else:
        # 解析对比日期（None = 使用默认昨天，[] = 不加对比线）
        compare_dates = None
        dt = datetime.strptime(date, "%Y-%m-%d")
        if args.compare_days and args.compare_days > 0:
            compare_dates = [(dt - timedelta(days=i)).strftime("%Y-%m-%d")
                             for i in range(1, args.compare_days + 1)]
        elif args.compare:
            if args.compare in ("yesterday", "auto"):
                compare_dates = [(dt - timedelta(days=1)).strftime("%Y-%m-%d")]
            else:
                compare_dates = [d.strip() for d in args.compare.split(",") if d.strip()]
        output = args.output or f"{safe_name}{type_suffix}-{date}.png"
        draw_hourly(date, display_name, components, project, output, compare_dates=compare_dates)

    # ── --notify: 出图后自动上传 S3 + 推送大象 ──
    if getattr(args, 'notify', None):
        misid = args.notify
        print(f"[notify] Uploading chart and sending to {misid}...", file=sys.stderr)
        img_url = upload_to_s3(output)

        # 计算对比总量（仅小时级模式有 compare_dates）
        compare_totals = None
        if not args.minute and not args.versions and not (args.time_range and re.match(r'(\d+)d', args.time_range or "")):
            # 小时级模式，尝试拉昨天数据算总量
            dt = datetime.strptime(date, "%Y-%m-%d")
            ref_dates = compare_dates if compare_dates is not None else [(dt - timedelta(days=1)).strftime("%Y-%m-%d")]
            compare_totals = {}
            for cdate in ref_dates:
                cnext = (datetime.strptime(cdate, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
                total = 0
                for comp_name in components.values():
                    raw = mcporter_query("perf.crash", f"{cdate} 00:00:00", f"{cnext} 00:00:00",
                                         [("project", project), ("default_component", comp_name)])
                    total += sum(aggregate_hourly(raw).values())
                compare_totals[cdate] = total

        # 计算今日 comp_sums（重新从 output 文件名无法获取，简单重查或从 stdout 解析）
        # 这里用简化方式：重查今日小时级数据
        next_day = (datetime.strptime(date, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
        comp_sums = {}
        sum_crash = 0
        for label, comp_name in components.items():
            raw = mcporter_query("perf.crash", f"{date} 00:00:00", f"{next_day} 00:00:00",
                                  [("project", project), ("default_component", comp_name)])
            s = sum(aggregate_hourly(raw).values())
            comp_sums[label] = s
            sum_crash += s

        mode_label = "分钟级" if args.minute else ("版本对比" if args.versions else (f"{args.time_range}趋势" if args.time_range else "小时级"))
        msg = build_notify_message(display_name, date, comp_sums, sum_crash,
                                    compare_totals=compare_totals, mode_label=mode_label)
        notify_daxiang(misid, msg, img_url=img_url)


if __name__ == "__main__":
    main()
