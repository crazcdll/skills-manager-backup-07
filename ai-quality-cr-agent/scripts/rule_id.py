#!/usr/bin/env python3
"""前端 Issue 规则来源校验与编号归一化；两份 Skill 保持同一实现。"""

import re

_RULE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]*$")
_KNOWN_PREFIXES = ("CR:", "MT:", "CU:", "L2:", "BL:", "FE:", "EXT:")
_SOURCE_SCOPES = {"platform": ("L1", "L2"), "project": ("L3",), "fallback": ("FALLBACK",)}


class RuleIdError(ValueError):
    def __init__(self, field, message):
        self.field = field
        super().__init__(f"{field}: {message}")


def _normalize_segment(value, field="ruleId"):
    if not isinstance(value, str) or not _RULE_ID.fullmatch(value.strip()):
        raise RuleIdError(field, "expected a non-empty ID using letters, digits, . _ : / or -")
    value = value.strip()
    if value.startswith(_KNOWN_PREFIXES):
        if not value.split(":", 1)[1]:
            raise RuleIdError(field, "rule prefix requires an ID")
        return value
    value = re.sub(r"(?i)^fe-l[12]:", "", value)
    if value.startswith("L3:"):
        value = "L3_" + value[3:]
    return "FE:" + value


def normalize_fe_rule_id(issue):
    """校验来源，合并全部规则编号；成功后一次性更新，不改动 rule_sources。"""
    if not isinstance(issue, dict) or issue.get("source") not in ("fe-ai-review", "fe_review"):
        return issue
    sources = issue.get("rule_sources")
    if not isinstance(sources, list):
        raise RuleIdError("rule_sources", "required array; use [] for pure-context findings")
    raw = issue.get("ruleId", "")
    if not isinstance(raw, str):
        raise RuleIdError("ruleId", "must be a string")
    if raw.strip() and not sources:
        raise RuleIdError("rule_sources", "rule hits must retain their sources")

    source_ids = []
    for index, source in enumerate(sources):
        field = f"rule_sources[{index}]"
        if not isinstance(source, dict):
            raise RuleIdError(field, "must be an object")
        for key in ("source_type", "scope_level", "file"):
            if not isinstance(source.get(key), str) or not source[key].strip():
                raise RuleIdError(f"{field}.{key}", "required non-empty string")
        if source["scope_level"] not in _SOURCE_SCOPES.get(source["source_type"], ()):
            raise RuleIdError(field, "source_type and scope_level do not match")
        upstream = source.get("upstream_rule_id", "")
        if not isinstance(upstream, str):
            raise RuleIdError(f"{field}.upstream_rule_id", "must be a string")
        upstream = upstream.strip()
        if source["scope_level"] == "L3":
            value = upstream[3:] if upstream.startswith("FE:") else upstream
            if value.startswith(("L3:", "L3_")):
                value = value[3:]
            rid = _normalize_segment("L3_" + (value or "custom"), f"{field}.upstream_rule_id")
        else:
            rid = _normalize_segment(upstream, f"{field}.upstream_rule_id")
        source_ids.append(rid)

    # FE 编号只从来源派生；原 ruleId 只保留混合审查中的非 FE 编号。
    other_prefixes = tuple(prefix for prefix in _KNOWN_PREFIXES if prefix != "FE:")
    other_ids = [_normalize_segment(part) for part in raw.split("+")
                 if part.strip().startswith(other_prefixes)]
    ids = list(dict.fromkeys(other_ids + source_ids))
    if "mergedRuleIds" in issue:
        merged = issue["mergedRuleIds"]
        if not isinstance(merged, list) or not all(isinstance(part, str) and part.strip() for part in merged):
            raise RuleIdError("mergedRuleIds", "must be an array of non-empty strings")
    issue["ruleId"] = " + ".join(ids)
    if "mergedRuleIds" in issue:
        issue["mergedRuleIds"] = list(ids)
    return issue
