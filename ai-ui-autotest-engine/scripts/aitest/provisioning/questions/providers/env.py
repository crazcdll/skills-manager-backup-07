#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""环境维度 provider —— 测试环境类型 + 资源 MIS + 泳道/域名映射。

规则表以 `provisioning/validators/env_validator.py` 的 `APP_ENV_TYPE_RULES`
为唯一事实来源；本 provider 只负责"声明问题 + 派生三维值"。

收集结果（intake）经 `env_validator.build_env_from_intake` 合成为 env 块，
是 env 配置的**唯一输入源**（AI 不再手写 steps-input.env）。

字段设计（场景名唯一说法见 `env_validator.ENV_SCENARIO_LABEL`）：
  · `env_type`           —— 环境类型（A/P/B/C/D/E，封闭选项）
                            A=线上基准；P=线上泳道；C=测试基准；
                            B=测试泳道；E=测试域名映射；D=免登录（认证维度）
  · `resource_mis`       —— 设备归属 / 报告 user_id（AppMock **运行域**由 `mis acquire` 从号池领取，
                            与场景 mockId 所属规则库恒定分离）；
                            能确定当前身份时自动派生（见 `shared.user_identity.current_user_mis`），否则退回必答
  · `swim_lane_name`     —— 泳道名（仅测试泳道 B；必填）
  · `swim_url_mappings`  —— 域名映射 JSON 数组（仅测试域名映射 E；必填）

泳道（B）与域名映射（E）是**两种独立环境，分开使用**：依赖条件由
`ENV_CAPABILITIES` 派生，换环境时 driver 会自动清掉不适用项。
"""
from aitest.shared.user_identity import current_user_mis
from aitest.provisioning.questions.registry import QuestionProvider, register_provider
from aitest.provisioning.validators.env_validator import (
    APP_ENV_TYPE_RULES, DEFAULT_APP, ENV_SCENARIO_OPTIONS, capability_depends_on,
)


def _env_type_options(app: str) -> list:
    """环境选择选项：默认 App 用统一场景表（含线上泳道），其他 App 按其注册表。"""
    if app == DEFAULT_APP:
        return [dict(item) for item in ENV_SCENARIO_OPTIONS]
    rules = APP_ENV_TYPE_RULES.get(app, {})
    return [
        {"value": code, "label": f"{code} — {rule['desc']}"}
        for code, rule in sorted(rules.items())
    ]


def _resource_mis_question(mis: str) -> dict:
    """资源 MIS 题：能确定当前身份就声明为 derived（自动落库、不提问），否则退回必答。

    可确定来源见 `shared.user_identity.current_user_mis()`（HOTEL_UI_MIS → 缓存的 SSO 身份 → git 身份）。
    derived 题**仍可被 `input-seed` 覆盖**（declared 题不受"派生键不可预置"限制），
    因此"改用其他 MIS"的能力保持不变。
    """
    base = {
        "id": "resource_mis", "group": "identity", "order": 20,
        "prompt": "资源 MIS（设备归属 / 报告 user_id）",
        "input_type": "text",
        # 允许用户经 input-seed 覆盖（覆盖后引擎不再重算），见 driver._apply_derived
        "overridable": True,
    }
    if mis:
        return {
            **base, "required": False, "source": "derived",
            "resolve": lambda _ctx: mis,
            "note": f"自动取自当前身份：{mis}（如需改用其他 MIS，可用 input-seed 覆盖）",
        }
    return {**base, "required": True, "source": "ask", "default": None}


@register_provider
class EnvQuestionProvider(QuestionProvider):
    name = "env"

    def questions(self, ctx) -> list:
        app = ctx.get("app") or DEFAULT_APP
        return [
            {
                "id": "env_type", "group": "env", "order": 10,
                "prompt": "选择测试环境（类型即场景，ptest 已归属类型 P，不再单独提问）",
                "input_type": "single", "required": True,
                "options": _env_type_options(app),
                "note": "线上基准=A；线上泳道=P；测试基准=C；测试泳道=B（泳道名）；测试域名映射=E；D=免登录（认证）",
            },
            _resource_mis_question(current_user_mis()),
            {
                "id": "swim_lane_name", "group": "scope", "order": 30,
                "prompt": "泳道名称（仅测试泳道 B，必填）",
                "input_type": "text", "required": True,
                # 仅 B 适用：条件由环境能力矩阵派生，不手写
                "depends_on": capability_depends_on("swim_lane_name"),
            },
            {
                "id": "swim_url_mappings", "group": "scope", "order": 31,
                "prompt": "域名映射 JSON 数组（仅测试域名映射 E，必填；如 "
                          "[{\"url\":\"域名\",\"betaUrl\":\"映射地址\"}]）",
                "input_type": "text", "required": True,
                "depends_on": capability_depends_on("swim_url_mappings"),
            },
        ]
