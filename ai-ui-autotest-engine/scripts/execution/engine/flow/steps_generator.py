#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""steps-input.json 生成器：接收业务数据，填充引擎逻辑，输出最终产物。

职责：sid 自动编号、blur-input 注入、intake 占位符替换、两级校验。
与 flow-init 的关系：本模块做生成期校验，flow-init 做执行期校验，不重复。

使用方式
--------
在轻量模板（.run/tasks/<task>/tmp/generate_steps.py）中：
    from execution.engine.flow.steps_generator import StepsGenerator
    gen = StepsGenerator(TAG, BATCH_NAME, DEVICE, ENV, CASES)
    path = gen.output()
"""
import os
import re

from shared.errors import PayloadError
from shared.paths import SKILL_DIR, steps_input_dir, flows_dir, resolve_input_path
from shared.intake import read_intake
from shared.json_utils import write_json_atomic, read_json
from shared.placeholders import collect_case_placeholder_text, extract_placeholders
from provisioning.validators.env_validator import build_env_from_intake

KIND_WHITELIST = {"ui", "api", "track"}
ENV_TYPE_WHITELIST = {"A", "B", "C", "D"}


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
        if not cases:
            raise ValueError("cases 不能为空")

        self.tag = tag
        self.batch_name = batch_name
        self.device = device
        self.env = dict(env or {})
        self.cases = cases
        self.flow_sources = flow_sources or []

    def run(self) -> dict:
        """执行生成流程，返回完整 steps-input dict。"""
        self._prepare_steps()
        self._inject_flow_sources()
        self._inject_env_from_intake()
        data = self._build_data()
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

    # ── env 合成：env 的唯一输入源 = intake ──────────────────────

    def _inject_env_from_intake(self):
        """用 intake 合成 env 块（type/auth_method/account/password/泳道/ptest/锁包）。

        AI 的 CASES 不再手写 env；此处与 `validate_steps_json` 共用同一实现
        （`build_env_from_intake`），保证「收集即所得」。
        """
        self.env = {**self.env, **build_env_from_intake(read_intake())}

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
          "resolved": ["deal_id"],        # 已在 intake 中有值的
          "unresolved": [{"name":"deal_id", "case_ids":["case_01", "case_02"]}],
          "all_resolved": true/false,      # 是否全部已解析
        }
        """
        answers = read_intake()

        found_map = {}  # {name: {case_ids: set}}
        for case in cases:
            cid = case.get("case_id", "")
            case_params = case.get("params", {}) or {}
            text = collect_case_placeholder_text(case)
            for ph in extract_placeholders(text):
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
            if name in answers:
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

    def _validate(self, data: dict):
        """两级校验：内置基础校验 + 引擎强校验。

        内置校验：配置非空、kind 白名单、断言必填、占位符格式、sid 冲突。
        引擎校验：委托 flow_init.validate_steps_json（action 白名单/字段互斥/effect 契约）。
        """
        errors = []

        if not data.get("batch_name"):
            errors.append("batch_name 未填写")
        env_type = (data.get("env") or {}).get("type")
        if env_type not in ENV_TYPE_WHITELIST:
            errors.append(
                f"env.type 非法: {env_type}，须为 {sorted(ENV_TYPE_WHITELIST)}"
                f"（env 由 intake 合成，请先收集 env_type）"
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
                if isinstance(pv, str) and extract_placeholders(pv):
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
            from execution.engine.flow.steps_builder import validate_steps_json
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
        """生成 steps-input-{tag}.json 并写入 .run/tasks/<task>/tmp/，返回文件路径。"""
        try:
            data = self.run()
        except ValueError as ve:
            # 已格式化的校验错误，直接抛出
            raise
        except Exception as e:
            # 未预期的异常：给出友好提示而非原始堆栈
            raise type(e)(f"steps-input 生成异常: {e}") from e
        
        out_dir = steps_input_dir()
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
            text = collect_case_placeholder_text(case)
            for ph in extract_placeholders(text):
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

        print("📋 待收集占位符（已登记为待收集项，通过 `input-next` 逐题收集）：")
        for p in unique:
            case_ids = [x["case_id"] for x in pending if x["placeholder"] == p["placeholder"]]
            print(f"   - {p['placeholder']}: {', '.join(case_ids)}")

        ph_path = os.path.join(out_dir, f"steps-input-{self.tag}.placeholders.json")
        write_json_atomic(ph_path, {"pending_placeholders": [p["placeholder"] for p in unique]})
        print(f"📄 占位符清单已输出: {ph_path}")
        if unique:
            print(
                "💡 逐题收集：<入口> input-next"
                "  （按返回的 next 指针用 input-answer 一题一答提交，禁止直接构造 input-answer）"
            )


# ── 工具函数 ──────────────────────────────────────────────────


def mask_password(env: dict) -> dict:
    """掩码密码等敏感字段，仅用于 stdout 展示，不改动写入数据。"""
    shown = dict(env)
    if shown.get("password"):
        shown["password"] = "******"
    return shown


def cases_json_path(tag: str) -> str:
    """返回 CASES JSON 的绝对路径（.run/tasks/<task>/tmp/cases-<tag>.json）。"""
    return os.path.join(steps_input_dir(), f"cases-{tag}.json")


def _create_empty_cases_file(path: str):
    """在磁盘上创建空 CASES JSON 文件（强制约定的第一步）。"""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as _f:
        pass


def cmd_cases_create(args):
    """cases-create 命令：强制约定 —— AI 写内容前必须先创建空 CASES 文件。

    为什么必须先用命令/终端创建空文件：
      AI 用编辑器「新建」文件时，内容可能尚未落盘，随后 steps-generate
      会读到空文件并因 JSON 解析失败而中断。先创建空文件可让 AI 的写入
      成为「修改已存在文件」，并留下明确的落盘校验入口。
    """
    tag = args.tag
    path = cases_json_path(tag)
    force = getattr(args, "force", False)

    if os.path.exists(path) and os.path.getsize(path) > 0 and not force:
        print(f"⚠️  已存在非空文件，跳过创建: {path}（{os.path.getsize(path)} 字节）")
        print("   如需重置为空文件，请加 --force")
        return

    _create_empty_cases_file(path)
    print(f"✅ 空 CASES 文件已创建: {path}")
    print("   强制约定：AI 写入完整 CASES（device/env/cases/steps）并确认落盘后，再执行：")
    print(f"   <入口> steps-generate --input 'cases-{tag}.json' --tag {tag}")


def cmd_steps_generate(args):
    """steps-generate 命令：接收 AI 编写的 CASES JSON，输出最终 steps-input.json。"""
    import json as _json

    # ── 归一化路径：裸文件名→本 workspace steps-input 目录；相对路径→SKILL_DIR ──
    raw = resolve_input_path(args.json)
    if not os.path.exists(raw):
        # 强制约定：不代 AI 造数据，只创建空文件占位并提示正确顺序
        _create_empty_cases_file(raw)
        print(f"✅ 空文件已创建: {raw}")
        print("   强制约定：AI 必须先写入完整 CASES 内容，确认落盘后再执行 steps-generate")
        return
    try:
        with open(raw, "r", encoding="utf-8") as _f:
            raw = _f.read()
    except Exception as e:
        raise PayloadError(f"ERROR: 读取文件失败: {e}") from e

    # 强制约定门禁：文件存在但为空 = AI 写入的内容尚未落盘
    if not raw.strip():
        raise PayloadError(
            "ERROR: CASES 文件存在但为空: {}\n"
            "  ⚠️ 强制约定：必须先用 `cases-create` 创建空文件，AI 写入内容并落盘后再执行本命令。\n"
            "  常见原因：编辑器写入尚未落盘，steps-generate 读到的仍是空文件。\n"
            "  处理步骤：\n"
            "    1) <入口> cases-create --tag <tag>\n"
            "    2) AI 写入完整 CASES 内容，并确认落盘（wc -c <file> 应 > 0）\n"
            "    3) 重新执行 steps-generate".format(raw)
        )

    try:
        data = _json.loads(raw)
    except _json.JSONDecodeError as e:
        raise PayloadError(f"ERROR: JSON 解析失败: {e}\n  文件: {raw}（{len(raw)} 字节）") from e

    # \u626b\u63cf .run/tasks/<task>/inputs/flows/ \u83b7\u53d6 .md \u6587\u4ef6\u5217\u8868
    flow_sources = []
    if os.path.isdir(flows_dir()):
        try:
            flow_sources = sorted(
                os.path.join(flows_dir(), f)
                for f in os.listdir(flows_dir())
                if f.endswith(".md") and os.path.isfile(os.path.join(flows_dir(), f))
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