#!/usr/bin/env python3
"""Legacy calculation only, plus a disconnected offline observation API.

No publisher/client imports, network, environment lookup or business writes.
Candidate keys are retrieval hints, NEVER evidence of semantic equivalence.
"""
import argparse
from collections import Counter
import copy
import hashlib
import json
import os
import re
import sys

# 解析规范化规则编号，并兼容历史评论中的后端裸编号，供 PR 评论去重使用。
# 新结果的规则编号由 rule_id.normalize_fe_rule_id() 统一生成。
_RULE_PATTERN = re.compile(
    r'\[((?:CR|MT|CU|L2|BL|FE|EXT):[A-Za-z0-9][A-Za-z0-9._:/-]*)\]'
    r'|(?:^|(?<=[\s*`\[(]))((?:CR|MT|CU|L2|BL|FE|EXT):[A-Za-z0-9][A-Za-z0-9._:/-]*)(?=[\s`\-\]\*,;)]|$)'
    r'|\[([A-Z][A-Z0-9]+-[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*)\]'
    r'|(?:^|(?<=[\s*`\[(]))([A-Z][A-Z0-9]+-[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*)(?=[\s`\-\]\*,;)]|$)'
    r'|(?:^|(?<=[\s*`\[(]))(java-l1:[A-Z]{2,4}-[0-9]{2,3}\.[A-Za-z0-9-]+)(?=[\s`\-\]\*,;)]|$)'
)

_P_LEVEL = re.compile(r"^P[0-3](?:-\d+)?$")


def _extract_rule_ids(text):
    """从评论文本中提取已经规范化的规则编号。"""
    matches = _RULE_PATTERN.findall(text or "")
    ids = [next((group for group in match if group), "") for match in matches]
    return [rid for rid in ids if rid and not _P_LEVEL.fullmatch(rid)]


def _comment_fp(text):
    """正文 SHA-256 指纹：只规范换行、首尾空白和首行问题序号。
    保留正文内空白、证据行号、严重级别及正文中的编号引用。"""
    t = (text or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    if not t:
        return ""
    title, separator, body = t.partition("\n")
    title = re.sub(
        r"^((?:#{1,6}[ \t]+)?(?:\*\*)?(?:[🚨🔴🟠🟡🔵][ \t]*)?)\[P([0-3])-\d+\]",
        r"\1[P\2]", title, count=1,
    )
    # 旧问号标题与新标签归一，避免仅展示文案/Q 编号变化导致重复评论。
    title = re.sub(
        r"^((?:#{1,6}[ \t]+)?)(?:❓[ \t]*|(?:🟡|🔎)[ \t]*待人工确认[ \t]*)\[Q-\d+\]",
        r"\1[Q]", title, count=1,
    )
    return hashlib.sha256((title + separator + body).encode("utf-8")).hexdigest()


def filter_duplicate_inline(inline_comments, existing_data, *, return_details=False):
    """旧三层过滤计算；默认返回旧二元组，details 仅供发布器保留日志。

    此粗过滤策略原样保留，不代表下方观察 API 的语义结论。
    输入对象不修改；kept 中仍保留原对象引用。
    """
    if existing_data is None:
        return (inline_comments, 0, 0, 0) if return_details else (inline_comments, 0)
    exact_set, fuzzy_set = existing_data
    kept = []
    skipped = 0
    skipped_exact = 0
    skipped_fuzzy = 0
    for c in inline_comments:
        file_ = c.get("file_keyword", "")
        file_key = (file_ or "").strip().lower()
        file_basename = os.path.basename(file_) if file_ else ""
        line = c.get("line", 0)
        text = c.get("text", "")
        issue = c.get("_issue") or {}
        if issue.get("severity") == "confirm" and issue.get("source") != "step4e":
            key = ("confirm", file_, line, c.get("line_type"), _comment_fp(text))
            if key in exact_set:
                skipped += 1
                skipped_exact += 1
            else:
                kept.append(c)
            continue
        rids = _extract_rule_ids(text)
        if not rids:
            # 无规则编号时仅凭位置无法区分独立风险，必须匹配评论正文指纹。
            fp = _comment_fp(text)
            if fp and _dedup_hit(fuzzy_set, file_key, file_basename, (fp,)):
                skipped += 1
                skipped_fuzzy += 1
                continue
        else:
            # Layer 1: 精确匹配 (file, line, ruleId)
            all_exact = all(_dedup_hit(exact_set, file_key, file_basename, (line, rid)) for rid in rids)
            if all_exact:
                skipped += 1
                skipped_exact += 1
                continue
            # Layer 2: 模糊兜底 (file, ruleId)，忽略行号
            all_fuzzy = all(_dedup_hit(fuzzy_set, file_key, file_basename, (rid,)) for rid in rids)
            if all_fuzzy:
                skipped += 1
                skipped_fuzzy += 1
                continue
        kept.append(c)
    if return_details:
        return kept, skipped, skipped_exact, skipped_fuzzy
    return kept, skipped


def _dedup_hit(key_set, file_key, file_basename, tail):
    """去重键匹配：优先完整路径，路径粒度不一致时回退 basename。
    key_set 元素结构为 (file, *tail)。两侧同为完整路径或同为 basename 时用原键；
    一侧完整路径一侧 basename 时追加 basename 键兼容旧数据，两侧都试不误判
    （不同目录同名文件仅在同粒度键下才会命中，精确层仍区分路径）。"""
    if (file_key, *tail) in key_set:
        return True
    if file_basename and file_basename != file_key:
        return (file_basename, *tail) in key_set
    return False


# Offline observation: semantic state and recommended action are distinct axes.
DIMENSIONS = ("responsibilityCode", "rootCause", "trigger", "failure", "impact", "recommendation")
STATES = ("SAME_UNCHANGED", "SAME_CHANGED", "INDEPENDENT", "UNKNOWN")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_COMMIT = re.compile(r"^[0-9a-f]{40}$")
_RAW_SOURCE_SLOTS = ("sourceReceipt", "raw", "source")


def content_digest(value):
    """Full JSON content hash; no dropping fields, whitespace or evidence items."""
    serialized = json.dumps(value, ensure_ascii=False, sort_keys=True,
                            separators=(",", ":"), allow_nan=False)
    try:
        encoded = serialized.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise ValueError("content cannot be encoded as UTF-8: " + str(exc)) from exc
    return hashlib.sha256(encoded).hexdigest()


def _nonempty(value):
    return isinstance(value, str) and bool(value.strip())


def make_binding(payload):
    """Bind run/PR, BOTH frozen endpoints, diff bytes hash, all final findings/history.

    Caller must supply sha256 of the frozen diff bytes, not a path or inferred hash.
    Invalid/missing input raises ValueError. No previous skip/decision is consumed.
    """
    context = payload.get("context")
    findings = payload.get("findings")
    history = payload.get("history")
    if not isinstance(context, dict) or not isinstance(findings, list) or not isinstance(history, dict):
        raise ValueError("context/findings/history missing or invalid")
    if not all(_nonempty(context.get(k)) for k in ("runId", "org", "repo")):
        raise ValueError("runId/org/repo required")
    pr_id = context.get("prId")
    if not ((type(pr_id) is int and pr_id > 0) or
            (isinstance(pr_id, str) and pr_id.isdigit() and int(pr_id) > 0)):
        raise ValueError("prId required")
    for key in ("fromHash", "toHash"):
        if not isinstance(context.get(key), str) or not _COMMIT.fullmatch(context[key]):
            raise ValueError("full frozen " + key + " required")
    if not isinstance(context.get("diffSha256"), str) or not _SHA256.fullmatch(context["diffSha256"]):
        raise ValueError("frozen diffSha256 required")
    if not all(isinstance(f, dict) for f in findings):
        raise ValueError("findings must contain full objects")
    if not isinstance(history.get("comments"), list) or not all(isinstance(c, dict) for c in history["comments"]):
        raise ValueError("history.comments full snapshot required")
    if not isinstance(history.get("receipt"), dict):
        raise ValueError("explicit history receipt required (legacy list is insufficient)")
    def _raw_digest_gate(label, snapshot):
        """raw 摘要配对门禁：仅对含 source/sourceSha256/comments/commentsSha256
        任一键的 dict 生效，不误伤无 raw 语义的普通 dict。

        source 数据键与 sourceSha256 声明必须成对出现且摘要一致（缺声明、缺
        数据、错配均 ValueError）；comments 仅在数据与声明同时存在时校验一致
        （规范化回执的 commentsSha256 语义指向 history.comments，允许不内嵌
        comments 槽）。平铺形状（receipt.source 与 receipt.sourceSha256 同级，
        history 顶层同理）与嵌套槽位快照共用本门禁。
        """
        if not any(key in snapshot for key in ("source", "sourceSha256", "comments", "commentsSha256")):
            return
        if ("source" in snapshot) != ("sourceSha256" in snapshot):
            raise ValueError(label + ": source/sourceSha256 pair required")
        if "source" in snapshot and snapshot["sourceSha256"] != content_digest(snapshot["source"]):
            raise ValueError(label + ": sourceSha256 mismatch against source")
        if ("comments" in snapshot and "commentsSha256" in snapshot
                and snapshot["commentsSha256"] != content_digest(snapshot["comments"])):
            raise ValueError(label + ": commentsSha256 mismatch against comments")

    raw_snapshots = {}
    for location, container in (("history", history), ("receipt", history["receipt"])):
        _raw_digest_gate(location, container)
        snapshots = {}
        for slot in _RAW_SOURCE_SLOTS:
            if slot not in container:
                continue
            snapshot = container[slot]
            if isinstance(snapshot, dict):
                _raw_digest_gate(location + "." + slot, snapshot)
            snapshots[slot] = copy.deepcopy(snapshot)
        if snapshots:
            raw_snapshots[location] = snapshots
    binding = {k: context[k] for k in ("runId", "org", "repo", "prId", "fromHash", "toHash", "diffSha256")}
    binding.update(contextSha256=content_digest(context), findingsSha256=content_digest(findings),
                   historySha256=content_digest(history),
                   historyRawSha256=content_digest(raw_snapshots) if raw_snapshots else None,
                   comparisonsSha256=content_digest(payload.get("comparisons", [])),
                   inputSha256=content_digest(payload), schemaVersion=1)
    return binding


def binding_valid(binding, payload):
    """Changes or missing fields invalidate prior observations; never reuse a skip."""
    try:
        return isinstance(binding, dict) and binding == make_binding(payload)
    except (ValueError, TypeError, OverflowError):
        return False


def _path(obj):
    # Exact full path hints only; basename collisions must not establish a match.
    path = obj.get("filePath") or obj.get("file_keyword") or obj.get("file") or ""
    return path if isinstance(path, str) else ""


def _hint_text(value):
    return value if isinstance(value, str) else ""


def retrieve_candidates(finding, comments):
    """Return hint-bearing indices only; absence of hints is NOT independence."""
    candidates = []
    path = _path(finding)
    text = (_hint_text(finding.get("text")) or _hint_text(finding.get("summary")) or
            _hint_text(finding.get("description")))
    rules = set(_extract_rule_ids(text) + _extract_rule_ids(_hint_text(finding.get("ruleId"))))
    fp = _comment_fp(text)
    for index, comment in enumerate(comments):
        reasons = []
        old_path = _path(comment)
        if path and path == old_path:
            reasons.append("full_path")
            if finding.get("line") is not None and finding.get("line") == comment.get("line"):
                reasons.append("same_line")
        elif path and old_path and os.path.basename(path) == os.path.basename(old_path):
            reasons.append("basename_only_not_proof")
        if rules.intersection(_extract_rule_ids(_hint_text(comment.get("text"))) +
                              _extract_rule_ids(_hint_text(comment.get("ruleId")))):
            reasons.append("rule_hint")
        if fp and fp == _comment_fp(_hint_text(comment.get("text"))):
            reasons.append("fingerprint_hint")
        if reasons:
            candidates.append({"historyIndex": index, "hints": reasons})
    return candidates


def _evidence_ok(evidence):
    """Strict, checkable paired evidence. Validation is NOT semantic verification."""
    if not isinstance(evidence, dict) or set(evidence) != set(DIMENSIONS):
        return False
    for dimension in DIMENSIONS:
        pair = evidence[dimension]
        if not isinstance(pair, dict) or set(pair) != {"current", "historical"}:
            return False
        for side in ("current", "historical"):
            record = pair[side]
            if not isinstance(record, dict) or set(record) != {"claim", "references"}:
                return False
            if not _nonempty(record["claim"]) or not isinstance(record["references"], list) or not record["references"]:
                return False
            for ref in record["references"]:
                if not isinstance(ref, dict) or set(ref) != {"file", "symbol", "commit", "startLine", "endLine", "quote"}:
                    return False
                if not all(_nonempty(ref[k]) for k in ("file", "symbol", "quote")):
                    return False
                if not isinstance(ref["commit"], str) or not _COMMIT.fullmatch(ref["commit"]):
                    return False
                if type(ref["startLine"]) is not int or type(ref["endLine"]) is not int or not (0 < ref["startLine"] <= ref["endLine"]):
                    return False
    return True


_LEDGER_STATUS = ("covered", "new", "changed", "unconfirmed")


def _ledger_ok(ledger, evidence):
    """Per-dimension evidence ledger; validation is NOT semantic verification.

    Every dimension must classify covered/new/changed/unconfirmed and map
    current/historical references as exact multisets of content_digest(ref),
    independently for each side and dimension (including duplicate counts).
    Digest equality proves content mapping only, not reference authenticity.
    basis arrays stay auxiliary explanation only.
    """
    if (not _evidence_ok(evidence) or not isinstance(ledger, dict) or
            set(ledger) != set(DIMENSIONS)):
        return False
    for dimension in DIMENSIONS:
        entry = ledger[dimension]
        if not isinstance(entry, dict) or set(entry) != {"status", "references"}:
            return False
        if entry["status"] not in _LEDGER_STATUS:
            return False
        refs = entry["references"]
        if not isinstance(refs, dict) or set(refs) != {"current", "historical"}:
            return False
        for side in ("current", "historical"):
            mapped = refs[side]
            if (not isinstance(mapped, list) or not mapped or
                    not all(isinstance(item, str) and _SHA256.fullmatch(item) for item in mapped)):
                return False
            # No missing, extra, forged or borrowed slots; preserve multiplicity.
            try:
                expected = Counter(content_digest(ref) for ref in evidence[dimension][side]["references"])
            except (ValueError, TypeError, OverflowError):
                return False
            if Counter(mapped) != expected:
                return False
    return True


def _verified_pair(pair, binding, finding, comment, verifier):
    """Trusted OFFLINE verifier is an explicit injection boundary, not JSON trust.

    CLI never supplies one. JSON verified=True / matching strings cannot pass.
    Verifier must independently inspect reference quotes/responsibility/causal chain
    and return an auditable bound result; it must be deterministic and side-effect free.
    """
    if not isinstance(pair, dict) or set(pair) != {"findingIndex", "historyIndex", "evidence"}:
        return None
    if not _evidence_ok(pair["evidence"]) or verifier is None:
        return None
    try:
        result = verifier(copy.deepcopy(pair), copy.deepcopy(binding), copy.deepcopy(finding), copy.deepcopy(comment))
        expected = {"state", "verifier", "basis", "bindingSha256", "pairSha256", "findingSha256", "commentSha256", "evidenceSha256"}
        # ledger 为可选键：存在时必须通过六维结构校验，否则整条结论作废
        if not isinstance(result, dict) or not set(result) <= expected | {"ledger"} or not set(result) >= expected:
            return None
        identity = result["verifier"]
        if not isinstance(identity, dict) or set(identity) != {"id", "version", "method"} or not all(_nonempty(v) for v in identity.values()):
            return None
        if result["state"] not in STATES[:-1]:
            return None
        basis = result["basis"]
        if (not isinstance(basis, dict) or set(basis) != set(DIMENSIONS) or
                not all(isinstance(v, list) and v and all(_nonempty(item) for item in v)
                        for v in basis.values())):
            return None
        for key, value in (("bindingSha256", binding), ("pairSha256", pair), ("findingSha256", finding),
                           ("commentSha256", comment), ("evidenceSha256", pair["evidence"])):
            if result[key] != content_digest(value):
                return None
        # 六维式逐项证据登记：verifier 提供 ledger 时必须结构合法（否则结论作废）；
        # 未提供 ledger 的可信 verifier 结论保留（basis 数组仍是可审计说明），
        # 但 REUSE 类结论仅在 ledger 全 covered 时才成立——见 observe 层门禁。
        if "ledger" in result and not _ledger_ok(result["ledger"], pair["evidence"]):
            return None
        return copy.deepcopy(result)
    except Exception:
        # Offline verification failure must not turn into reuse.
        return None



def _serialization_error(result):
    """Keep diagnostics even when the full observation is not valid JSON."""
    return {"schemaVersion": 1, "actualAction": "observe_only",
            "error": "serialization_failed", "errors": copy.deepcopy(result.get("errors", []))}


def observe(payload, *, verifier=None):
    """Keep EVERY finding/evidence, recommend only; never send/update comments.

    Completeness strictly requires receipt.complete is True and budgetExhausted
    is False, with a content-bound receipt. Unknown recommends NEW (not skip).
    Candidates only prioritize retrieval; independence needs all history verified.
    Pair conclusions from JSON alone are ignored. Prior decisions are not read.
    """
    findings = payload.get("findings", [])
    history = payload.get("history", {})
    comments = history.get("comments", []) if isinstance(history, dict) else []
    if not isinstance(comments, list):
        comments = []
    errors = []
    try:
        binding = make_binding(payload)
    except (ValueError, TypeError, OverflowError) as exc:
        binding = None
        errors.append(str(exc))
    receipt = history.get("receipt", {}) if isinstance(history, dict) else {}
    context = payload.get("context")
    context = context if isinstance(context, dict) else {}
    complete = (binding is not None and isinstance(receipt, dict) and receipt.get("complete") is True and
                receipt.get("budgetExhausted") is False and
                receipt.get("commentsSha256") == content_digest(comments) and
                all(type(receipt.get(k)) is type(context.get(k)) and receipt.get(k) == context.get(k)
                    for k in ("org", "repo", "prId")))
    if not complete:
        errors.append("history completeness unconfirmed or budget exhausted")
    pairs = payload.get("comparisons", [])
    comparisons_valid = isinstance(pairs, list)
    if not comparisons_valid:
        errors.append("comparisons must be an array")
        pairs = []
    results = []
    for index, finding in enumerate(findings if isinstance(findings, list) else []):
        valid_finding = isinstance(finding, dict)
        try:
            candidates = retrieve_candidates(finding, comments) if valid_finding and all(isinstance(c, dict) for c in comments) else []
        except UnicodeEncodeError as exc:
            candidates = []
            errors.append("candidate hint cannot be encoded as UTF-8: " + str(exc))
        validations = []
        state, recommended = "UNKNOWN", "NEW"
        pair_results = {}
        if binding is not None and complete and comparisons_valid and verifier is not None and valid_finding and bool(finding):
            for pair in pairs:
                if not isinstance(pair, dict) or type(pair.get("findingIndex")) is not int or pair["findingIndex"] != index:
                    continue
                hi = pair.get("historyIndex")
                if type(hi) is not int or not 0 <= hi < len(comments):
                    continue
                verified = _verified_pair(pair, binding, finding, comments[hi], verifier)
                # Multiple/conflicting assertions for one pair invalidate it.
                if hi in pair_results:
                    pair_results[hi] = None
                else:
                    pair_results[hi] = verified
                validations.append({"historyIndex": hi, "verification": verified,
                                    "evidence": copy.deepcopy(pair.get("evidence"))})
            confirmed = [r["state"] for r in pair_results.values() if r is not None]
            same = [s for s in confirmed if s in ("SAME_UNCHANGED", "SAME_CHANGED")]
            # Full historical coverage prevents a partial/contradictory set from authorizing reuse.
            covered = len(pair_results) == len(comments) and all(r is not None for r in pair_results.values())
            if covered:
                ledger_block = None
                if len(same) == 1:
                    # 逐项证据登记状态门禁：unconfirmed/new 阻断结论，
                    # changed 只允许 SAME_CHANGED→GLOBAL_SUPPLEMENT，不得 REUSE
                    statuses = []
                    for r in pair_results.values():
                        if r is not None and isinstance(r.get("ledger"), dict):
                            statuses.extend(e.get("status") for e in r["ledger"].values()
                                            if isinstance(e, dict))
                    if "unconfirmed" in statuses or "new" in statuses:
                        ledger_block = "unconfirmed-or-new-evidence"
                    elif "changed" in statuses and same[0] == "SAME_UNCHANGED":
                        ledger_block = "changed-evidence-not-reuse"
                    elif same[0] == "SAME_UNCHANGED" and not any(
                            r["state"] == "SAME_UNCHANGED" and isinstance(r.get("ledger"), dict)
                            and all(entry["status"] == "covered" for entry in r["ledger"].values())
                            for r in pair_results.values()):
                        # REUSE 必须由匹配 pair 自身的完整 ledger 全 covered 支持；
                        # 其他 pair 的 ledger 或 basis 不能补足匹配 pair 缺项。
                        ledger_block = "missing-itemized-ledger"
                    if ledger_block is None:
                        state = same[0]
                        recommended = "REUSE" if state == "SAME_UNCHANGED" else "GLOBAL_SUPPLEMENT"
                elif not same:
                    state = "INDEPENDENT"
                # Multiple historical matches require reconciliation; remain UNKNOWN.
        results.append({"findingIndex": index, "finding": copy.deepcopy(finding), "semanticState": state,
                        "recommendedAction": recommended, "actualAction": "observe_only",
                        "candidates": candidates, "verifications": validations,
                        "reason": "offline verifier conclusion" if state != "UNKNOWN" else "insufficient/invalid/unverified evidence"})
    output = {"schemaVersion": 1, "actualAction": "observe_only", "binding": binding,
              "bindingValid": binding is not None, "historyComplete": complete,
              "errors": errors, "results": results,
              "inputSnapshot": copy.deepcopy(payload)}
    try:
        json.dumps(output, ensure_ascii=False, allow_nan=False)
    except (ValueError, TypeError, OverflowError):
        return _serialization_error(output)
    return output


def main(argv=None):
    parser = argparse.ArgumentParser(description="Offline observation only; JSON claims are never trusted semantic verification")
    parser.add_argument("--input", required=True, help="local JSON file, or - for stdin")
    args = parser.parse_args(argv)
    if args.input == "-":
        payload = json.load(sys.stdin)
    else:
        with open(args.input, encoding="utf-8") as source:
            payload = json.load(source)
    if not isinstance(payload, dict):
        parser.error("input must be a JSON object")
    output = observe(payload)
    try:
        serialized = json.dumps(output, ensure_ascii=False, allow_nan=False)
    except (ValueError, TypeError, OverflowError):
        output = _serialization_error(output)
        serialized = json.dumps(output, ensure_ascii=False, allow_nan=False)
    # Preserve invalid input surrogates as JSON escapes, never emit invalid UTF-8.
    print(serialized.encode("utf-8", errors="backslashreplace").decode("utf-8"))
    return 1 if output.get("error") == "serialization_failed" else 0


if __name__ == "__main__":
    sys.exit(main())
