#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""steps-input.json 生成器：接收业务数据，填充引擎逻辑，输出最终产物。

职责：sid 自动编号、blur-input 注入、env_answers 占位符替换、两级校验。
与 flow-init 的关系：本模块做生成期校验，flow-init 做执行期校验，不重复。

使用方式
--------
在轻量模板（.run/tmp/generate_steps.py）中：
    from core.flow.steps_generator import StepsGenerator
    gen = StepsGenerator(TAG, BATCH_NAME, DEVICE, ENV, CASES)
    path = gen.output()
"""
import json
import os
import re

from core.errors import PayloadError
from core.util.paths import SKILL_DIR, STEPS_INPUT_DIR, FLOWS_DIR
from core.util.case_utils import read_env_answers
from core.util.json_utils import write_json_atomic, read_json
from core.placeholder.placeholder_resolver import _substitute_in_dict, _substitute_in_text

# 与 placeholder_resolver 保持一致的事实来源正则
_PLACEHOLDER_RE = re.compile(r'\{(\w+)\}')

# 断言中可能需要占位符替换的文本字段（与 AssertionSpec 字段保持一致）
_ASSERT_TEXT_FIELDS = ("expect", "criteria", "on_fail")

KIND_WHITELIST = {"ui", "api", "track"}
ENV_TYPE_WHITELIST = {"A", "B", "C", "D"}


def _substitute_assert_fields(assert_item, params):
    """对单条断言做占位符替换（仅替换已存在的字段，绝不新增键）。

    历史实现在这里无条件写入 "text": ""，把旧 schema 的空字段塞进每一条断言，
    并一路带到 steps-input.json / flow-context.json / 报告快照中。
    """
    item = dict(assert_item)
    for field in _ASSERT_TEXT_FIELDS:
        value = item.get(field)
        if isinstance(value, str) and value:
            item[field] = _substitute_in_text(value, params)
    targets = item.get("targets")
    if isinstance(targets, list):
        item["targets"] = [
            _substitute_in_text(target, params) if isinstance(target, str) else target
            for target in targets
        ]
    return item


class StepsGenerator:
    """接收业务数据，输出完整 steps-input JSON。

    支持前置扫描模式（--pre-scan）：在步骤转化前扫描占位符，
    输出未解析的 {xxx} 清单，供 AI 收集数据后再正式生成。

    参数：
        tag: 输出文件 tag（最终文件：steps-input-<TAG>.json）
        batch_name: 批次名称（对应 batch_name，报告中展示）
        device: 设备配置 dict
        env: 环境配置 dict
        cases: Case 列表（每个元素含 steps 数组）
    """

    def __init__(self, tag: str, batch_name: str, device: dict, env: dict, cases: list, flow_sources: list = None):
        if not tag:
            raise ValueError("tag 不能为空")
        if not batch_name:
            raise ValueError("batch_name 不能为空")
        if not device:
            raise ValueError("device 不能为空")
        if not env:
            raise ValueError("env 不能为空")
        if not cases:
            raise ValueError("cases 不能为空")

        self.tag = tag
        self.batch_name = batch_name
        self.device = device
        self.env = env
        self.cases = cases
        self.flow_sources = flow_sources or []

    def run(self) -> dict:
        """执行生成流程，返回完整 steps-input dict。"""
        self._prepare_steps()
        self._inject_flow_sources()
        self._inject_env_answers()
        data = self._build_data()
        data = self._substitute_placeholders(data)
        self._validate(data)
        return data

    # ── flow_source 注入：将 .md 文件路径写入每个 case ──────────

    def _inject_flow_sources(self):
        """将 flow_sources 中的 .md 路径按顺序写入每个 case 的 flow_source 字段（AI 未手动填写时）。

        flow_sources 与 cases 按索引一一对应，不足时只覆盖前 N 个 case。
        """
        for i, case in enumerate(self.cases):
            if i < len(self.flow_sources) and self.flow_sources[i]:
                if not case.get("flow_source"):
                    case["flow_source"] = os.path.normpath(self.flow_sources[i])

    # ── env 可选字段注入：从 env_answers 自动补全 AI 漏填的字段 ────

    def _inject_env_answers(self):
        """从 env_answers.json 自动注入已收集的 env 可选字段（如 ptest、bundle_lock）。

        AI 在 CASES JSON 中显式填写的值优先，未填写的从已保存的答案中自动补全。
        """
        answers = read_env_answers()
        INJECT_KEYS = {"ptest", "bundle_lock"}
        for key in INJECT_KEYS:
            if key not in self.env and key in answers:
                self.env[key] = answers[key]

    # ── 步骤预处理 ──────────────────────────────────────────────

    def _prepare_steps(self):
        """自动补全 sid + 为 input-text 注入 blur-input。

        分两步：
        1. 自动编号（S/A/T 前缀，手写 sid 的保持不变）
        2. 为每个 input-text 步骤在其后注入 blur-input（依赖其 sid）
        """
        # 第一步：编号
        for case in self.cases:
            steps = case.get("steps", [])
            # 收集已手写的 sid，自动编号时跳过占用，避免冲突
            used = set(s.get("sid") for s in steps if s.get("sid"))
            si = ai = ti = 0

            for step in steps:
                if step.get("sid"):
                    continue
                kind = step.get("kind", "ui")
                # 递增计数器直到拿到未占用 sid（跳过手写占用的编号）
                while True:
                    if kind == "ui":
                        si += 1
                        cand = f"S{si}"
                    elif kind == "api":
                        ai += 1
                        cand = f"A{ai}"
                    else:
                        ti += 1
                        cand = f"T{ti}"
                    if cand not in used:
                        step["sid"] = cand
                        used.add(cand)
                        break

        # 第二步：注入 blur（编号完成后才能确定 sid）
        for case in self.cases:
            new_steps = []
            for step in case.get("steps", []):
                new_steps.append(step)
                if step.get("action") == "input-text":
                    new_steps.append({
                        "sid": f"{step['sid']}_blur",
                        "kind": "ui",
                        "desc": "blur（输入后自动失焦触发校验）",
                        "action": "blur-input",
                        "action_arg": step.get("action_anchor", ""),
                        "step-type": "interaction",
                    })
            case["steps"] = new_steps

    # ── 数据组装 ────────────────────────────────────────────────

    def _build_data(self) -> dict:
        return {
            "batch_name": self.batch_name,
            "device": self.device,
            "env": self.env,
            "cases": self.cases,
        }

    # ── 占位符替换 ──────────────────────────────────────────────

    def _substitute_placeholders(self, data: dict) -> dict:
        """替换 {xxx} 占位符 — 先 Case 级 params 再全局 env_answers。"""
        env_answers = read_env_answers()
        for case in data.get("cases", []):
            case_params = case.get("params", {}) or {}
            if not case_params:
                continue
            # 仅替换该 Case 的 landing_scheme 和 steps 字段
            case["landing_scheme"] = _substitute_in_text(case.get("landing_scheme", ""), case_params)
            for step in case.get("steps", []):
                for field in ("action_arg", "action_anchor", "wait_text"):
                    if step.get(field):
                        step[field] = _substitute_in_text(step[field], case_params)
                for field in ("asserts",):
                    if step.get(field):
                        step[field] = [
                            _substitute_assert_fields(a, case_params)
                            for a in step[field] if isinstance(a, dict)
                        ]
                for field in ("track_assert", "api_assert"):
                    val = step.get(field)
                    if val:
                        step[field] = _substitute_in_dict(val, case_params)
            del case["params"]
        if env_answers:
            data = _substitute_in_dict(data, env_answers)
        return data

    # ── 前置占位符扫描（步骤转化前的门禁节点） ─────────────────────

    @staticmethod
    def scan_placeholders(cases: list) -> dict:
        """前置扫描：不生成步骤，只扫描 CASES 中的 {xxx} 占位符。

        作为步骤转化前的门禁节点，在 AI 写完 CASES 后、正式生成前调用。
        扫描结果用于 AI 判断需要向用户收集哪些数据。

        参数：
            cases: CASES 定义（每个元素含 flow_content / landing_scheme / steps）

        返回: {
          "found": [{"name":"deal_id", "case_ids":["case_01"], "description":""}],
          "resolved": ["deal_id"],        # 已在 env_answers.json 中有值的
          "unresolved": [{"name":"deal_id", "case_ids":["case_01", "case_02"]}],
          "all_resolved": true/false,      # 是否全部已解析
        }
        """
        env_answers = read_env_answers()

        found_map = {}  # {name: {case_ids: set}}
        for case in cases:
            cid = case.get("case_id", "")
            case_params = case.get("params", {}) or {}
            text = _collect_placeholder_text(case)
            for ph in _PLACEHOLDER_RE.findall(text):
                if ph in case_params:
                    continue  # 已由 Case 级 params 覆盖，无需收集
                if ph not in found_map:
                    found_map[ph] = {"case_ids": set()}
                found_map[ph]["case_ids"].add(cid)

        found_list = []
        unresolved_list = []
        resolved_list = []

        for name in sorted(found_map.keys()):
            info = found_map[name]
            entry = {
                "name": name,
                "case_ids": sorted(info["case_ids"]),
            }
            found_list.append(entry)
            if name in env_answers:
                resolved_list.append(name)
            else:
                unresolved_list.append(entry)

        return {
            "found": found_list,
            "resolved": resolved_list,
            "unresolved": unresolved_list,
            "all_resolved": len(unresolved_list) == 0,
        }

    # ── 校验 ────────────────────────────────────────────────────

    def _collect_placeholder_text(self, case: dict) -> str:
        """收集 case 中所有可能含 {xxx} 占位符的字段，拼接为完整文本。"""
        return _collect_placeholder_text(case)

    def _validate(self, data: dict):
        """两级校验：内置基础校验 + 引擎强校验。

        内置校验：配置非空、kind 白名单、断言必填、占位符格式、sid 冲突。
        引擎校验：委托 flow_init.validate_steps_json（action 白名单/字段互斥/effect 契约）。
        """
        errors = []

        if not data.get("batch_name"):
            errors.append("batch_name 未填写")
        if data["env"]["type"] not in ENV_TYPE_WHITELIST:
            errors.append(
                f"env.type 非法: {data['env']['type']}，须为 {sorted(ENV_TYPE_WHITELIST)}"
            )
        if not data["cases"]:
            errors.append("cases 为空：请按 Flow 填写至少一个 Case")

        # ── 断言覆盖率提示（纯计数对比，不含语义，不阻断） ────────
        for case in data["cases"]:
            cid = case.get("case_id", "?")
            md_path = case.get("flow_source") or ""
            if not md_path or not os.path.isfile(md_path):
                continue
            try:
                with open(md_path, "r", encoding="utf-8") as _fh:
                    md_text = _fh.read()
            except OSError:
                continue
            md_checks = len(re.findall(r'^- .+?」', md_text, re.MULTILINE))
            json_asserts = sum(
                len(step.get("asserts", []) or [])
                for step in case.get("steps", [])
                if isinstance(step.get("asserts"), list)
            )
            if md_checks > json_asserts:
                print(
                    f"⚠️  [{cid}] 断言覆盖率提示：Flow .md 含 {md_checks} 个校验点，"
                    f"CASES JSON 仅 {json_asserts} 个断言，差 {md_checks - json_asserts} 个"
                )
                print(
                    "   仅供参考，AI 请自行判断是否需要补充 asserts。"
                )

        for case in data["cases"]:
            if not case.get("case_id") or not case.get("case_name"):
                errors.append("case 缺少 case_id 或 case_name")
            if not case.get("landing_scheme", "").startswith("imeituan://"):
                errors.append(
                    f"{case.get('case_id')}: landing_scheme 必须以 imeituan:// 开头"
                )
            for pk, pv in (case.get("params", {}) or {}).items():
                if isinstance(pv, str) and _PLACEHOLDER_RE.search(pv):
                    errors.append(f"{case.get('case_id')}: params.{pk} 含占位符，须为确定值")
            seen_sids = set()
            for step in case.get("steps", []):
                kind = step.get("kind", "ui")
                if kind not in KIND_WHITELIST:
                    errors.append(f"{case['case_id']}: kind 非法 {kind} (sid={step.get('sid')})")
                if kind == "ui":
                    if not step.get("action"):
                        errors.append(
                            f"{case['case_id']}/{step.get('sid')}: ui 步骤缺少 action"
                        )
                if step.get("step-type") == "assert" and not (
                    step.get("asserts")
                ):
                    errors.append(
                        f"{case['case_id']}/{step.get('sid')}: "
                        "step-type=assert 步骤必须提供至少一项断言"
                    )
                elif kind == "api" and not step.get("api_assert"):
                    errors.append(
                        f"{case['case_id']}/{step.get('sid')}: api 步骤缺少 api_assert"
                    )
                elif kind == "track":
                    ta = step.get("track_assert")
                    if not ta or not isinstance(ta, dict) or "match" not in ta:
                        errors.append(
                            f"{case['case_id']}/{step.get('sid')}: track_assert 必须包含 \"match\" 字段，正确示例: {{\"track_assert\":{{\"match\":\"事件名\"}}}}"
                        )
                # sid 冲突检测
                sid = step.get("sid")
                if sid:
                    if sid in seen_sids:
                        errors.append(f"{case['case_id']}: sid 重复 {sid}")
                    seen_sids.add(sid)

        if errors:
            raise ValueError(
                "steps-input 结构自校验失败：\n" + "\n".join(f"  - {e}" for e in errors)
            )

        # 引擎强校验：委托 flow_init.validate_steps_json
        try:
            from core.flow.steps_builder import validate_steps_json
            validate_steps_json(dict(data))
        except ValueError as ve:
            # 结构化错误提示：提取关键信息，不暴露堆栈
            error_msg = str(ve)
            # 常见错误模式 → 解决方案映射
            # 提示：新增校验时在此追加错误→解决方案映射
            hints = []
            if "device" in error_msg.lower() and "组合" in error_msg:
                hints.append("  💡 设备组合不支持，可选: sandbox-android-meituan / local-harmony-meituan / local-android-meituan")
            if "landing_scheme" in error_msg.lower():
                hints.append("  💡 每个 Case 必须提供 landing_scheme（落地页 Scheme）")
            if "env.type" in error_msg.lower():
                hints.append("  💡 env.type 必填，可选值: A(线上) / B(泳道) / C(alpha) / D(免登录)")
            
            hint_text = "\n".join(hints) if hints else ""
            raise ValueError(f"{error_msg}{hint_text}")
        except ImportError:
            # 引擎校验器不可用，回退到内置校验（不阻塞）
            pass

    # ── 输出 ────────────────────────────────────────────────────

    def output(self) -> str:
        """生成 steps-input-{tag}.json 并写入 .run/tmp/，返回文件路径。"""
        try:
            data = self.run()
        except ValueError as ve:
            # 已格式化的校验错误，直接抛出
            raise
        except Exception as e:
            # 未预期的异常：给出友好提示而非原始堆栈
            raise type(e)(f"steps-input 生成异常: {e}") from e
        
        out_dir = STEPS_INPUT_DIR
        os.makedirs(out_dir, exist_ok=True)
        out_path = os.path.join(out_dir, "steps-input-{}.json".format(self.tag))

        write_json_atomic(out_path, data)

        # 回读验证
        read_json(out_path)

        # 输出占位符信息
        self._output_placeholder_info(data, out_dir)

        return out_path

    def _output_placeholder_info(self, data: dict, out_dir: str):
        """输出占位符清单（打印 + 结构化 JSON），供 AI 直接发起 AskQuestion。"""
        pending = []
        for case in data.get("cases", []):
            text = self._collect_placeholder_text(case)
            for ph in sorted(set(_PLACEHOLDER_RE.findall(text))):
                pending.append({"case_id": case.get("case_id"), "placeholder": ph})

        seen = set()
        unique = []
        for p in pending:
            if p["placeholder"] not in seen:
                seen.add(p["placeholder"])
                unique.append(p)

        if not unique:
            print("✅ 所有占位符已解析，无需收集。")
            return

        print("📋 待收集占位符（请向用户提问，收集后执行 save-answers 持久化）：")
        for p in unique:
            case_ids = [x["case_id"] for x in pending if x["placeholder"] == p["placeholder"]]
            print(f"   - {p['placeholder']}: {', '.join(case_ids)}")

        ph_path = os.path.join(out_dir, f"steps-input-{self.tag}.placeholders.json")
        write_json_atomic(ph_path, {"pending_placeholders": [p["placeholder"] for p in unique]})
        print(f"📄 占位符清单已输出: {ph_path}")
        if unique:
            print(
                "💡 收集后执行: "
                f"python3 scripts/cli.py save-answers "
                f'--answers \'{{"{unique[0]["placeholder"]}":"<值>"}}\''
            )


# ── 工具函数 ──────────────────────────────────────────────────


def _collect_placeholder_text(case: dict) -> str:
    """收集 case 中所有可能含 {xxx} 占位符的字段，拼接为完整文本。

    覆盖字段：landing_scheme（跳链）、steps 各字段，以及断言的
    expect / criteria / on_fail / targets（新断言 schema 下文案在这些字段里）。
    历史实现只扫断言的 text 字段，新 schema 下会漏掉断言里的占位符，
    使占位符门禁失效。
    """
    texts = [case.get("landing_scheme", "")]
    for s in case.get("steps", []):
        texts.append(s.get("action_arg", ""))
        texts.append(s.get("action_anchor", ""))
        texts.append(s.get("wait_text", ""))
        for field in ("asserts",):
            for a in s.get(field, []):
                if isinstance(a, dict):
                    for text_field in _ASSERT_TEXT_FIELDS:
                        texts.append(a.get(text_field, ""))
                    for target in a.get("targets") or []:
                        if isinstance(target, str):
                            texts.append(target)
        for field in ("track_assert", "api_assert"):
            val = s.get(field)
            if val:
                texts.append(json.dumps(val, ensure_ascii=False))
    return "\n".join(texts)


def mask_password(env: dict) -> dict:
    """掩码密码等敏感字段，仅用于 stdout 展示，不改动写入数据。"""
    shown = dict(env)
    if shown.get("password"):
        shown["password"] = "******"
    return shown


def cmd_steps_generate(args):
    """steps-generate 命令：接收 AI 编写的 CASES JSON，输出最终 steps-input.json。"""
    import json as _json

    # ── 归一化路径：相对路径基于 SKILL_DIR，不受 CWD 影响 ──────────
    raw = args.json
    if not os.path.isabs(raw):
        raw = os.path.normpath(os.path.join(SKILL_DIR, raw))
    try:
        with open(raw, "r", encoding="utf-8") as _f:
            raw = _f.read()
    except FileNotFoundError:
        os.makedirs(os.path.dirname(raw), exist_ok=True)
        with open(raw, "w", encoding="utf-8") as _f:
            pass
        print(f"\u2705 \u7a7a\u6587\u4ef6\u5df2\u521b\u5efa: {raw}")
        print(f"   AI \u8bf7\u5199\u5165\u5b8c\u6574 steps \u5185\u5bb9\u540e\u91cd\u65b0\u6267\u884c steps-generate")
        return
    except Exception as e:
        raise PayloadError(f"ERROR: 读取文件失败: {e}") from e
    try:
        data = _json.loads(raw)
    except _json.JSONDecodeError as e:
        raise PayloadError(f"ERROR: JSON 解析失败: {e}") from e

    # \u626b\u63cf .run-input/flows/ \u83b7\u53d6 .md \u6587\u4ef6\u5217\u8868
    flow_sources = []
    if os.path.isdir(FLOWS_DIR):
        try:
            flow_sources = sorted(
                os.path.join(FLOWS_DIR, f)
                for f in os.listdir(FLOWS_DIR)
                if f.endswith(".md") and os.path.isfile(os.path.join(FLOWS_DIR, f))
            )
        except OSError:
            pass

    gen = StepsGenerator(
        tag=args.tag,
        batch_name=data.get("batch_name", ""),
        device=data.get("device", {}),
        env=data.get("env", {}),
        cases=data.get("cases", []),
        flow_sources=flow_sources,
    )
    out_path = gen.output()
    print(f"\u2705 steps-input \u5df2\u751f\u6210: {out_path}")