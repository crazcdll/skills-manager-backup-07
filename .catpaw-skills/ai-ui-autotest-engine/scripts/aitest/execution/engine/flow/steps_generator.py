#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""steps-input.json 生成器：接收业务步骤模型，填充引擎逻辑，输出最终产物。

职责：sid 自动编号、blur-input 注入、intake 占位符替换、两级校验。
与 flow-init 的关系：本模块做生成期校验，flow-init 做执行期校验，不重复。

入参是 `steps.json`（业务真源，见 ai-app-flow `scripts/steps/model.py`）：
业务模型 → 引擎 CASES 的映射由 `execution.engine.flow.flow_json.to_batch` 完成，
**在命令内部一次走完**，不存在「AI 手写 CASES 再喂进来」的中间环节。

使用方式
--------
    from aitest.execution.engine.flow.steps_generator import StepsGenerator
    gen = StepsGenerator(TAG, BATCH_NAME, DEVICE, ENV, CASES)
    path = gen.output()
"""
import json
import os

from aitest.shared.errors import PayloadError
from aitest.shared.input_freeze import freeze_inputs
from aitest.shared.paths import steps_input_dir, resolve_input_path
from aitest.shared.intake import read_intake
from aitest.shared.json_utils import write_json_atomic, read_json
from aitest.shared.placeholders import (
    collect_case_placeholder_text,
    extract_placeholders,
    validate_var_spec,
)
from aitest.provisioning.validators.env_validator import build_env_from_intake

KIND_WHITELIST = {"ui", "api", "track"}
ENV_TYPE_WHITELIST = {"A", "B", "C", "D"}


def _blur_anchor(step: dict) -> str:
    """input-text 的失焦锚点：优先 action_anchor，其次取 action_arg JSON 里的 anchor。"""
    anchor = str(step.get("action_anchor") or "").strip()
    if anchor:
        return anchor
    raw = str(step.get("action_arg") or "").strip()
    if not raw:
        return ""
    try:
        payload = json.loads(raw)
    except (ValueError, TypeError):
        return raw
    if isinstance(payload, dict):
        return str(payload.get("anchor") or "").strip()
    return raw


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

    def __init__(self, tag: str, batch_name: str, device: dict, env: dict, cases: list):
        if not tag:
            raise ValueError("tag 不能为空")
        if not batch_name:
            raise ValueError("batch_name 不能为空")
        if not cases:
            raise ValueError("cases 不能为空")

        self.tag = tag
        self.batch_name = batch_name
        # device 允许缺省：由 intake 合成（业务模型 steps.json 不描述设备形态）
        self.device = dict(device or {})
        self.env = dict(env or {})
        self.cases = cases

    def run(self) -> dict:
        """执行生成流程，返回完整 steps-input dict。"""
        self._prepare_steps()
        self._inject_env_from_intake()
        self._inject_device_from_intake()
        data = self._build_data()
        self._validate(data)
        return data

    # ── 设备组合：env 与 device 同源（intake）────────────────────

    # ── env 合成：env 的唯一输入源 = intake ──────────────────────

    def _inject_device_from_intake(self):
        """设备组合：缺省时由 intake 合成，与 flow-init 的默认值保持同口径。"""
        if self.device:
            return
        intake = read_intake() or {}
        self.device = {
            "type": str(intake.get("device_type") or "sandbox"),
            "platform": str(intake.get("platform") or "android"),
            "app": str(intake.get("app") or "meituan"),
        }

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
        # 锚点取 action_anchor（手写 CASES）；steps.json 映射来的 input-text 是
        # `{"anchor": ..., "text": ...}` JSON，需要取出 anchor 再当失焦锚点。
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
                        "action_arg": _blur_anchor(step),
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
            cases: CASES 定义（每个元素含 landing_scheme / steps）

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
            case_vars = case.get("vars", {}) or {}
            text = collect_case_placeholder_text(case)
            for ph in extract_placeholders(text):
                spec = case_vars.get(ph) or {}
                if spec and spec.get("ask") is not True:
                    continue  # 已由 vars.value / vars.date 固定，无需收集
                if ph not in found_map:
                    found_map[ph] = {
                        "case_ids": set(),
                        "description": str(spec.get("desc") or ""),
                    }
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
            if info.get("description"):
                entry["description"] = info["description"]
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

        # 断言只来自 CASES JSON（steps.json 是唯一真源）

        for case in data["cases"]:
            if not case.get("case_id") or not case.get("case_name"):
                errors.append("case 缺少 case_id 或 case_name")
            if not case.get("landing_scheme", "").startswith("imeituan://"):
                errors.append(
                    f"{case.get('case_id')}: landing_scheme 必须以 imeituan:// 开头"
                )
            for vk, spec in (case.get("vars") or {}).items():
                case_id = case.get("case_id")
                errors.extend(validate_var_spec(
                    vk, spec, where=f"{case_id}: vars.{vk}"
                ))
            declared = set((case.get("vars") or {}).keys())
            missing = [
                ph for ph in extract_placeholders(collect_case_placeholder_text(case))
                if ph not in declared
            ]
            if missing:
                errors.append(
                    f"{case.get('case_id')}: 占位符 {missing} 未在 vars 声明"
                    "（固定值用 value，需执行前填写用 ask）"
                )
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
            from aitest.execution.engine.flow.steps_builder import validate_steps_json
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
        """生成 steps-input-{tag}.json 并写入 $STATE/run/tasks/<task>/tmp/，返回文件路径。"""
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
        """输出待收集占位符（仅 vars.ask），供 AI 直接发起 AskQuestion。"""
        pending = []
        fixed = []
        for case in data.get("cases", []):
            case_vars = case.get("vars") or {}
            for ph in extract_placeholders(collect_case_placeholder_text(case)):
                spec = case_vars.get(ph) or {}
                if spec and spec.get("ask") is not True:
                    if ph not in fixed:
                        fixed.append(ph)
                    continue
                pending.append({"case_id": case.get("case_id"), "placeholder": ph})

        if fixed:
            print(f"📌 已固定变量（vars.value / vars.date，不再提问）：{', '.join(fixed)}")


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


def cmd_steps_generate(args):
    """steps-generate：`steps.json`（业务真源）→ `steps-input.json`。

    业务模型 → 引擎 CASES 的映射在这里一次完成（`flow_json.to_batch`），
    因此不存在「AI 先手写一份 CASES 文件、再喂给引擎」的中间态：少一个环节，
    就少一类「漏跑/写错形状」的失败模式。

    路径口径与其它命令一致：绝对路径原样；裸文件名 → workspace `tmp/`；
    含目录的相对路径 → SKILL_DIR。编排层的用例快照用绝对路径直接传入。
    """
    import json as _json

    from aitest.execution.engine.flow.flow_json import FlowJsonError, to_batch

    raw = resolve_input_path(args.steps)
    if not os.path.exists(raw):
        raise PayloadError(
            f"ERROR: steps.json 不存在: {raw}\n"
            "  提示：steps.json 由 ai-app-flow 产出，落盘前先跑 "
            "`python3 scripts/steps_cli.py check --in <steps.json> --no-upload`"
        )
    try:
        with open(raw, "r", encoding="utf-8") as _f:
            flow = _json.load(_f)
    except _json.JSONDecodeError as e:
        raise PayloadError(f"ERROR: steps.json 解析失败: {e}\n  文件: {raw}") from e
    except OSError as e:
        raise PayloadError(f"ERROR: 读取文件失败: {e}") from e

    try:
        batch = to_batch(flow)
    except FlowJsonError as e:
        raise PayloadError(
            f"ERROR: steps.json → CASES 映射失败（{raw}）:\n  {e}"
        ) from e

    gen = StepsGenerator(
        tag=args.tag,
        batch_name=batch.get("batch_name", ""),
        device=batch.get("device", {}),
        env=batch.get("env", {}),
        cases=batch.get("cases", []),
    )
    out_path = gen.output()
    print(f"\u2705 steps-input \u5df2\u751f\u6210: {out_path}")

    # ── 输入冻结（初始化期唯一时机）──────────────────────────────
    # 上游 `.docs/` / `.orchestration/` 都按 keep-latest-N 滚动清理，执行之后再按原路径
    # 读取随时可能 404。这里把业务真源与刚生成的引擎输入一起复制进 workspace，
    # 后续 case-init / gen-report / archive_run 只认 workspace 内的相对路径。
    try:
        frozen = freeze_inputs(
            source_steps_path=raw,
            tag=args.tag,
            steps_input_path=out_path,
            case_ids=[case.get("case_id") for case in batch.get("cases", [])],
        )
    except OSError as e:
        raise PayloadError(
            f"ERROR: 输入冻结失败（steps.json → workspace inputs/）: {e}\n"
            f"  源文件: {raw}\n"
            "  报告需要这份原文，冻结失败会导致报告缺输入，因此这里直接失败"
        ) from e
    frozen_dir = os.path.dirname(frozen["files"][0]["path"])
    print(f"\U0001F4C4 \u8f93\u5165\u5df2\u51bb\u7ed3: {frozen_dir} "
          f"({', '.join(item['name'] for item in frozen['files'])})")