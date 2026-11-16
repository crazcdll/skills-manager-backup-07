#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""runner_identity —— 触发 Agent / 会话 ID 统一取值（展示与落库共用）。

抽离自 publish_results.py（）,逻辑零变更。
设计约定:
- agent_name: --agent-name 显式传参 → env X_AI_PAAS（官方语义=Agent 名）→ env 1024_PAAS 兜底;
  白名单校验: 合法 agent 名一律 AICR_Agent 开头, 非该前缀的值(数字员工账号等非 Agent 实例名)
  视为无效丢弃并继续下一来源, 无合法值时留空不上送
- session_id: --session-id 显式传参 → 与 conversation_id 同源嗅探
  （仅当 conversation_id 未显式传入时复用;显式传不代表同值）
- 两信息均拿不到返回空串,调用方按「不展示不阻断」处理
- URL 格式: 主页 /agent/{a}/overview; 会话细则 /agent/{a}/log/chat/{sid}/analysis?view=turns
"""
import os
import sys
from urllib.parse import quote as _url_quote

# ── 触发 Agent / 会话 ID 公共取值（展示与落库共用同一来源, 避免漂移）────────────
# 合法 agent 名白名单前缀: agent 名一律 AICR_Agent 开头,
# 数字员工账号(mis)等非 Agent 实例名一律拦截, 不写入落库字段
AGENT_NAME_PREFIX = "AICR_Agent"


def _clean_agent_name(value):
    """白名单校验单个候选值; 不规范(非 AICR_Agent 开头)丢弃并告警, 返回空串。"""
    v = (value or "").strip()
    if not v:
        return ""
    if not v.startswith(AGENT_NAME_PREFIX):
        print(f"⚠️ runner_identity: agent_name 候选值 '{v}' 不符合 AICR_Agent 前缀规范, 已丢弃",
              file=sys.stderr)
        return ""
    return v


def get_agent_name(args):
    """agent_name: --agent-name 显式传参 → env X_AI_PAAS（官方语义=Agent 名）→ env 1024_PAAS 兜底。
    每个来源经 _clean_agent_name 白名单校验(AICR_Agent 前缀), 不规范值丢弃后继续下一来源。"""
    for cand in (getattr(args, "agent_name", "") or "",
                 os.environ.get("X_AI_PAAS", ""),
                 os.environ.get("1024_PAAS", "")):
        v = _clean_agent_name(cand)
        if v:
            return v
    return ""


def get_session_id(args, conversation_id_from_env):
    """session_id: --session-id 显式传参 → 与 conversation_id 同源嗅探
    （仅当 conversation_id 来自 env 嗅探时复用; 显式传 conversation_id 不代表同值）"""
    sid = ((getattr(args, "session_id", "") or "")).strip()
    if not sid and conversation_id_from_env:
        sid = conversation_id_from_env
    return sid


AGENT_BASE_URL = "https://1024.sankuai.com/agent"


def agent_overview_url(agent_name):
    """Agent 主页链接（agent_name 做 URL path 编码, 非 ASCII 名不炸链接）。"""
    return f"{AGENT_BASE_URL}/{_url_quote(str(agent_name), safe='')}/overview"


def session_analysis_url(agent_name, session_id):
    """会话分析页链接（会话细则）。"""
    a = _url_quote(str(agent_name), safe="")
    sid = _url_quote(str(session_id), safe="")
    return f"{AGENT_BASE_URL}/{a}/log/chat/{sid}/analysis?view=turns"


def sniffed_conversation_id():
    """env 嗅探会话 ID（与 conversation_id 同源链路）。"""
    return os.environ.get("X_AI_SESSIONID", "").strip() or os.environ.get("rootConversationId", "").strip()


def agent_and_session(args):
    """统一取 (agent_name, session_id)——学城/大象/全局评论展示与 Step 9 落库共用同一来源。

    session_id 仅当 conversation_id 未显式传入时复用 env 嗅探链路（显式传
    conversation_id 不代表 session_id 同值）。两个信息均拿不到时返回空串,
    调用方按「不展示不阻断」处理。
    """
    an = get_agent_name(args)
    cid_env = "" if (args.conversation_id or "").strip() else sniffed_conversation_id()
    sid = get_session_id(args, cid_env)
    return an, sid
