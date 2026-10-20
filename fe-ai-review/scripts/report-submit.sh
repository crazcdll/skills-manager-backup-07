#!/usr/bin/env bash
# report-submit.sh — 上报 CR 结果到 AI CR 看板
#
# 用法：
#   bash report-submit.sh <payload_file>   # 推荐：从临时文件读取 JSON
#   bash report-submit.sh -                # 从 stdin 读取 JSON
#

set -euo pipefail

ENDPOINT="https://db0fvyryu3vkmafudd.database.sankuai.com/rest/v1/cr_reports"

# ANON_KEY 是 Supabase anon public key（非 service_role），设计上允许公开。
# Supabase 网关强制要求请求先带合法 JWT 表明身份（此处 role=anon）才能匹配 RLS 策略，否则脚本完全无法连接数据库
ANON_KEY="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJyb2xlIjoiYW5vbiIsImlzcyI6InN1cGFiYXNlIiwiaWF0IjoxNzQ2OTc5MjAwLCJleHAiOjE5MDQ3NDU2MDB9.nSp0KYl0X2mkZ5PMT3jnFBQmzhUOI4pEPzw0eyV4eq8"

INPUT="${1:-}"

if [[ -z "$INPUT" ]]; then
  echo "usage:" >&2
  echo "  bash report-submit.sh <payload_file>   # read JSON from file" >&2
  echo "  bash report-submit.sh -                # read JSON from stdin" >&2
  exit 1
fi

if [[ "$INPUT" == "-" ]]; then
  PAYLOAD=$(cat)
elif [[ -f "$INPUT" ]]; then
  PAYLOAD=$(cat "$INPUT")
  [[ "$INPUT" == /tmp/* ]] && rm -f "$INPUT"
else
  echo "error: file not found: $INPUT" >&2
  exit 1
fi

# 统一规则 ID。质量门禁看板接入后复用标准化后的 PAYLOAD。
PAYLOAD=$(printf '%s' "$PAYLOAD" | python3 -c '
import hashlib
import json
import sys

try:
    payload = json.load(sys.stdin)
except json.JSONDecodeError as error:
    raise SystemExit(f"error: invalid CR report JSON: {error}")

findings = payload.get("findings")
if not isinstance(findings, dict):
    raise SystemExit("error: findings must be an object")

bundle = findings.get("rule_bundle")
if not isinstance(bundle, dict):
    raise SystemExit("error: findings.rule_bundle is required")
if bundle.get("schema_version") != "cr-rule-source/v1":
    raise SystemExit("error: findings.rule_bundle.schema_version must be cr-rule-source/v1")
if bundle.get("source") not in {"mt-code-standards-setup", "fallback"}:
    raise SystemExit("error: findings.rule_bundle.source is invalid")
if bundle.get("standard_domain") != "frontend":
    raise SystemExit("error: findings.rule_bundle.standard_domain must be frontend")

source = bundle["source"]
snapshot_id = bundle.get("snapshot_id")
release_refs = bundle.get("release_refs")
if not isinstance(release_refs, list):
    raise SystemExit("error: findings.rule_bundle.release_refs must be an array")
if source == "mt-code-standards-setup":
    if not isinstance(snapshot_id, str) or not snapshot_id.strip():
        raise SystemExit("error: platform rule bundle requires snapshot_id")
    if not release_refs:
        raise SystemExit("error: platform rule bundle requires release_refs")
elif snapshot_id is not None:
    raise SystemExit("error: fallback rule bundle snapshot_id must be null")

release_keys = set()
for ref in release_refs:
    if not isinstance(ref, dict):
        raise SystemExit("error: every release_ref must be an object")
    key = (ref.get("scope_level"), ref.get("rule_set_id"), ref.get("release_id"))
    if not all(isinstance(value, str) and value.strip() for value in key):
        raise SystemExit("error: every release_ref needs scope_level, rule_set_id and release_id")
    release_keys.add(key)

project_rules = bundle.get("project_rules", [])
if not isinstance(project_rules, list):
    raise SystemExit("error: findings.rule_bundle.project_rules must be an array")
project_keys = set()
for rule in project_rules:
    if not isinstance(rule, dict):
        raise SystemExit("error: every project_rule must be an object")
    key = (rule.get("rule_set_id"), rule.get("rule_version"), rule.get("file"))
    if not all(isinstance(value, str) and value.strip() for value in key):
        raise SystemExit("error: every project_rule needs rule_set_id, rule_version and file")
    project_keys.add(key)

fallback = bundle.get("fallback")
if not isinstance(fallback, dict) or not isinstance(fallback.get("active"), bool):
    raise SystemExit("error: findings.rule_bundle.fallback.active must be boolean")
if fallback["active"]:
    fallback_set = fallback.get("rule_set_id")
    fallback_version = fallback.get("rule_version")
    if not isinstance(fallback_set, str) or not fallback_set.strip() or not isinstance(fallback_version, str) or not fallback_version.strip():
        raise SystemExit("error: active fallback requires rule_set_id and rule_version")
    if source != "fallback":
        raise SystemExit("error: active fallback requires findings.rule_bundle.source=fallback")
elif source == "fallback":
    raise SystemExit("error: fallback rule bundle requires fallback.active=true")

required_fields = ("source_type", "scope_level", "rule_set_id", "rule_version", "file", "title")
for level in ("p0", "p1", "p2p3"):
    entries = findings.get(level, [])
    if not isinstance(entries, list):
        raise SystemExit(f"error: findings.{level} must be an array")
    for entry in entries:
        if not isinstance(entry, dict):
            raise SystemExit(f"error: every findings.{level} entry must be an object")
        sources = entry.get("rule_sources")
        if not isinstance(sources, list):
            raise SystemExit("error: every finding must include rule_sources (use [] for context-only findings)")
        for rule in sources:
            if not isinstance(rule, dict):
                raise SystemExit("error: every rule_source must be an object")
            if not all(isinstance(rule.get(field), str) and rule[field].strip() for field in required_fields):
                raise SystemExit("error: rule_source is missing required identity fields")
            source_type = rule["source_type"]
            scope = rule["scope_level"]
            rule_set = rule["rule_set_id"]
            version = rule["rule_version"]
            file_name = rule["file"]
            if source_type == "platform":
                if scope not in {"L1", "L2"} or (scope, rule_set, version) not in release_keys:
                    raise SystemExit("error: platform rule_source must reference release_refs")
            elif source_type == "project":
                if scope != "L3" or (rule_set, version, file_name) not in project_keys:
                    raise SystemExit("error: project rule_source must reference project_rules")
            elif source_type == "fallback":
                if not fallback["active"] or scope != "FALLBACK" or rule_set != fallback.get("rule_set_id") or version != fallback.get("rule_version"):
                    raise SystemExit("error: fallback rule_source is invalid")
            else:
                raise SystemExit("error: rule_source.source_type is invalid")
            identity = {
                "source_type": source_type,
                "scope_level": scope,
                "rule_set_id": rule_set,
                "rule_version": version,
                "file": file_name,
                "section": rule.get("section", ""),
            }
            computed_id = "cr-rule/v1/" + hashlib.sha256(
                json.dumps(identity, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest()
            if rule.get("rule_id") not in (None, computed_id):
                raise SystemExit("error: rule_source.rule_id does not match canonical identity")
            rule["rule_id"] = computed_id

print(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
') || exit 1

RESP_FILE=$(mktemp /tmp/cr_report_response_XXXXXX.json)

HTTP_STATUS=$(printf '%s' "$PAYLOAD" | curl -s \
  -o "$RESP_FILE" \
  -w "%{http_code}" \
  -X POST "$ENDPOINT" \
  -H "apikey: $ANON_KEY" \
  -H "Authorization: Bearer $ANON_KEY" \
  -H "Content-Type: application/json" \
  -H "Prefer: return=representation" \
  --data-binary @-)

if [[ "$HTTP_STATUS" =~ ^2 ]]; then
  RECORD_ID=$(python3 -c "
import json
try:
    data = json.load(open('$RESP_FILE'))
    print(data[0]['id'] if isinstance(data, list) and data else '')
except Exception:
    print('')
" 2>/dev/null || echo "")
  if [[ -n "$RECORD_ID" ]]; then
    echo "[ok] CR report submitted (id: $RECORD_ID)"
  else
    echo "[ok] CR report submitted"
  fi
  rm -f "$RESP_FILE"
  exit 0
fi

BODY=$(cat "$RESP_FILE" 2>/dev/null || echo "(no body)")
rm -f "$RESP_FILE"
echo "[err] CR report failed (HTTP $HTTP_STATUS): $BODY" >&2
exit 1
