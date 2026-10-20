#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""报告层通用时间解析与耗时计算（parse_time / duration_ms）。"""
from datetime import datetime


def parse_time(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return None


def duration_ms(start, end):
    start_time = parse_time(start)
    end_time = parse_time(end)
    if not start_time or not end_time:
        return None
    return max(0, int((end_time - start_time).total_seconds() * 1000))
