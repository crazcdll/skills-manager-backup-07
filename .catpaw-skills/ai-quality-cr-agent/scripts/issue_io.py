#!/usr/bin/env python3
"""Validate and load review issues without performing any publishing actions."""

import argparse
import json
import os
import sys

from rule_id import RuleIdError, normalize_fe_rule_id


SEVERITY_ORDER = {"P0": 0, "P1": 1, "P2": 2, "P3": 3, "confirm": 4}
SOURCE_PREFIXES = {
    "step4a": ("CR:",),
    "step4b": ("MT:",),
    "step4c": ("CU:", "L2:"),
    "step4d": ("BL:",),
    "fe-ai-review": ("FE:",),
    "step4e": ("EXT:",),
}
REQUIRED_TEXT_FIELDS = (
    "severity", "ruleId", "anomalyType", "summary", "file", "lineType",
    "description", "risk", "suggestion", "source",
)
OPTIONAL_TEXT_FIELDS = (
    "code", "ruleName", "ruleFile", "reach_analysis", "online_scenario",
    "impact_scope", "confirm_reason", "possible_risk", "confirm_suggestion",
    "reviewVerdict", "reviewNote", "preReviewSeverity",
)


class IssueValidationError(ValueError):
    """An issues input is missing, malformed, or violates the issue schema."""


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise IssueValidationError("duplicate JSON object field")
        result[key] = value
    return result


def _reject_constant(value):
    raise IssueValidationError("non-standard JSON numeric constant")


def _error(location, field, message):
    raise IssueValidationError(f"{location}: {field}: {message}")


def _require_text(issue, field, location, allow_empty=False):
    if field not in issue:
        _error(location, field, "required field is missing")
    value = issue[field]
    if not isinstance(value, str):
        _error(location, field, "must be a string")
    if not allow_empty and not value.strip():
        _error(location, field, "must not be empty")


def validate_issue(issue, location="issue"):
    """Return a normalized copy of one issue, or raise IssueValidationError."""
    if not isinstance(issue, dict):
        raise IssueValidationError(f"{location}: each issue must be a JSON object")
    result = dict(issue)
    for field in REQUIRED_TEXT_FIELDS:
        _require_text(result, field, location, allow_empty=field == "ruleId")
    for field in OPTIONAL_TEXT_FIELDS:
        if field in result and not isinstance(result[field], str):
            _error(location, field, "must be a string when present")

    severity = result["severity"].strip()
    result["severity"] = "confirm" if severity.lower() == "confirm" else severity.upper()
    if result["severity"] not in SEVERITY_ORDER:
        _error(location, "severity", "must be P0, P1, P2, P3, or confirm; resolve ranges such as P2-P3 upstream")
    result["source"] = result["source"].strip()
    if result["source"] not in SOURCE_PREFIXES:
        _error(location, "source", "must be step4a, step4b, step4c, step4d, step4e, or fe-ai-review")
    if result["source"] == "fe-ai-review":
        try:
            normalize_fe_rule_id(result)
        except RuleIdError as exc:
            raise IssueValidationError(f"{location}: {exc}") from exc
    result["lineType"] = result["lineType"].strip().upper()
    if result["lineType"] not in ("ADDED", "REMOVED"):
        _error(location, "lineType", "must be ADDED or REMOVED")
    if "line" not in result or type(result["line"]) is not int or result["line"] < 1:
        _error(location, "line", "must be a positive integer")

    result["ruleId"] = result["ruleId"].strip()
    rule_ids = [item.strip() for item in result["ruleId"].split(" + ")] if result["ruleId"] else []
    if not rule_ids and result["source"] not in ("step4a", "fe-ai-review"):
        _error(location, "ruleId", "only step4a or fe-ai-review pure-context issues may use an empty ruleId")
    if rule_ids:
        allowed = tuple(p for tup in SOURCE_PREFIXES.values() for p in tup)
        for rule_id in rule_ids:
            if not any(rule_id.startswith(prefix) and rule_id[len(prefix):].strip()
                       for prefix in allowed):
                _error(location, "ruleId", "each rule must use a non-empty CR:, MT:, CU:, L2:, BL:, FE:, or EXT: identifier")
        if not any(rule_id.startswith(SOURCE_PREFIXES[result["source"]]) for rule_id in rule_ids):
            _error(location, "ruleId", "rule prefix must match source (including merged rules)")
        result["ruleId"] = " + ".join(rule_ids)

    if "mergedRuleIds" in result:
        merged = result["mergedRuleIds"]
        if not isinstance(merged, list) or not all(isinstance(item, str) and item.strip() for item in merged):
            _error(location, "mergedRuleIds", "must be an array of non-empty strings")
        if merged and set(merged) != set(rule_ids):
            _error(location, "mergedRuleIds", "must match the identifiers in ruleId")
    if result["source"] in ("step4b", "step4c"):
        for field in ("ruleName", "ruleFile"):
            _require_text(result, field, location)
    if result["severity"] in ("P0", "P1") and result["source"] != "step4e":
        # step4e(外部专项审查)豁免: SOP findings 契约仅 11 个基础字段,
        # 无 reach_analysis/online_scenario/impact_scope;试点期已降级 P2,
        # 转正后也不因此拒收(否则外部 skill 产出永远过不了门禁)
        for field in ("reach_analysis", "online_scenario", "impact_scope"):
            _require_text(result, field, location)
    if result["severity"] == "confirm" and result["source"] != "step4e":
        # 同上: confirm 的三字段也是内置路产出要求,EXT 契约无此字段
        for field in ("confirm_reason", "possible_risk", "confirm_suggestion"):
            _require_text(result, field, location)
    if "reviewVerdict" in result and result["reviewVerdict"] not in (
        "CONFIRM", "ESCALATE", "DOWNGRADE", "DISMISS", "OPEN_QUESTION", "BL_Q1_GATE",
    ):
        _error(location, "reviewVerdict", "unsupported review verdict")
    if "preReviewSeverity" in result and result["preReviewSeverity"] not in ("P0", "P1", "P2", "P3"):
        _error(location, "preReviewSeverity", "must be P0, P1, P2, or P3")
    return result


def load_issues(paths):
    """Load all declared inputs atomically; never skip a failed input or finding.

    Deduplicate only equal issue content (apart from severity), keeping the
    highest severity. Location or rule ID alone never identifies a finding.
    """
    if isinstance(paths, (str, bytes, os.PathLike)):
        raise IssueValidationError("issues paths must be a sequence of file paths")
    try:
        paths = list(paths)
    except TypeError as exc:
        raise IssueValidationError("issues paths must be a sequence of file paths") from exc
    if not paths:
        raise IssueValidationError("at least one issues file is required; use a file containing [] for no issues")

    deduped = {}
    for path in paths:
        if not isinstance(path, (str, os.PathLike)) or not os.fspath(path):
            raise IssueValidationError("each issues path must be a non-empty file path")
        try:
            with open(path, "r", encoding="utf-8") as stream:
                data = json.load(stream, object_pairs_hook=_unique_object, parse_constant=_reject_constant)
        except json.JSONDecodeError as exc:
            raise IssueValidationError(f"{path}: invalid JSON at line {exc.lineno}, column {exc.colno}: {exc.msg}") from exc
        except (OSError, UnicodeError, IssueValidationError) as exc:
            raise IssueValidationError(f"{path}: {exc}") from exc
        if not isinstance(data, list):
            if isinstance(data, dict) and data.get("schema") == "step4e-envelope/v1":
                # step4e 封装体——顶层是 {schema,status,error,findings,checks};
                # 校验器只消费 findings(逐条 schema 校验不变),状态判定归 publish 门禁。
                data = list(data.get("findings") or [])
            else:
                raise IssueValidationError(f"{path}: top-level value must be a JSON array")
        for index, issue in enumerate(data):
            normalized = validate_issue(issue, f"{path}[{index}]")
            identity = {key: value for key, value in normalized.items() if key != "severity"}
            key = json.dumps(identity, sort_keys=True, ensure_ascii=False, allow_nan=False)
            previous = deduped.get(key)
            if previous is None or SEVERITY_ORDER[normalized["severity"]] < SEVERITY_ORDER[previous["severity"]]:
                deduped[key] = normalized
    return sorted(deduped.values(), key=lambda issue: SEVERITY_ORDER[issue["severity"]])


def main(argv=None):
    parser = argparse.ArgumentParser(description="Validate issue JSON syntax and schema; performs no publishing actions.")
    parser.add_argument("paths", nargs="+", help="Issue JSON files; each must contain an array")
    args = parser.parse_args(argv)
    try:
        issues = load_issues(args.paths)
    except IssueValidationError as exc:
        print(f"Issue validation failed: {exc}", file=sys.stderr)
        return 1
    print(f"Validated {len(issues)} issues from {len(args.paths)} files")
    return 0


if __name__ == "__main__":
    sys.exit(main())
