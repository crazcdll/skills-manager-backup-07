#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""MeituanHarmonyAppDescriptor — 美团 HarmonyOS App 描述符实现。

封装美团鸿蒙版 App 的 bundleName、EntryAbility、AppMock URI、Scheme 前缀等常量。

与 Android 版本的关键差异：
  - main_activity_class 语义变为 abilityName（如 "EntryAbility"），
    main_activity 返回 "bundleName/abilityName" 形式，供 HarmonyOps.launch_app 使用。
  - debug_overlay_prefixes 为 ArkWeb/ArkUI 组件类名，
    与 Android 视图体系类名完全不同，已按真机实测结果校准。

新增其他 App（如点评鸿蒙版）时，在同目录下新建一个文件（如 dianping.py），
并在 devices/registry.py::_APP_REGISTRY 追加一行注册，不需要改动本文件。
"""
from devices.base import AppDescriptor


class MeituanHarmonyAppDescriptor(AppDescriptor):
    """美团 HarmonyOS App 描述符。

    包名随【设备形态 form】变化：真机/云真机用企业包（com.sankuai.hmeituan.beta），
    模拟器用正式包名（com.sankuai.hmeituan，非 enterprise）。form 由
    devices/registry.py 从 device_type 派生并经 context.create_app_descriptor()
    注入，与 apk_sources.json 的 real / emulator 两通道一一对应，避免包名在多处
    硬编码导致探测串包。
    """

    # 真机/云真机：企业签名包（走 HPX 企业安装页）
    _PACKAGE_REAL = "com.sankuai.hmeituan.beta"
    # 模拟器：非 enterprise 包名（走 L1 制品缓存 → 设备侧缓存 → `bm install -p`，
    # 云模拟器忽略签名；对应制品必须是可测性 debug HAP，见 references/apk_sources.json）
    _PACKAGE_EMULATOR = "com.sankuai.hmeituan"
    _ABILITY_NAME = "EntryAbility"

    @property
    def platform(self) -> str:
        return "harmony"

    @property
    def package_name(self) -> str:
        """包名按设备形态解析：真机企业包 / 模拟器正式包。"""
        return self._PACKAGE_EMULATOR if self.form == "emulator" else self._PACKAGE_REAL

    @property
    def main_activity_class(self) -> str:
        """鸿蒙下语义为 abilityName（不含包名前缀）。"""
        return self._ABILITY_NAME

    @property
    def appmock_content_uri(self) -> str:
        """鸿蒙无 ContentProvider 体系，AppMock 走 scheme 通道，此字段保留占位。"""
        return f"content://{self.package_name}.appmock/mock"

    @property
    def debug_overlay_prefixes(self) -> tuple:
        # TODO(harmony): 待开启调试面板/MRN 调试浮层后用 uitest dumpLayout
        # 实测真实 type 值后补齐，暂无可用样本。
        return ()

    @property
    def scheme_prefix(self) -> str:
        return "imeituan://www.meituan.com"

    def is_foreground(self, focus: str) -> bool:
        """鸿蒙同一 Ability 内路由切换不产生新的窗口标识，无法像 Android
        MainActivity 那样精确到具体页面，退化为"App 包名在前台即视为命中"。
        """
        return self.package_name in focus

    def foreground_confirmed_hint(self) -> str:
        return "鸿蒙无法区分具体页面，按 App 前台判定"

    @property
    def page_specs(self) -> dict:
        """登录页 / 验证码页描述（**数据**）。

        鸿蒙侧特征（实测）：同一 Ability 内路由切换**不改窗口标识**（焦点串只有 bundle name
        → `markers` 为空，身份只能按**内容**判定）；且页面**几乎不暴露 resource-id**
        （登录页仅 normalTextInput/navRoot/ffpRoot）→ 选择器 `role`/`text` 优先。

        这份数据就是"鸿蒙差异"的全部所在：登录业务层（`qahome.py`）不感知以上任何一点。
        """
        from devices.interfaces.page_spec import (PAGE_LOGIN, PAGE_LOGIN_CODE,
                                                 PageSpec, Route, Hop)

        return {
            PAGE_LOGIN: PageSpec(
                name="meituan-login@harmony",
                identity=[{"by": "text", "value": "获取验证码"},
                          {"by": "text", "value": "密码登录"},
                          {"by": "text", "value": "请输入手机号"}],
                markers=(),
                controls={
                    "phone_input": [{"by": "id", "value": "normalTextInput"},
                                    {"by": "role", "value": ["TextInput", "EditText"]}],
                    "send_code":   [{"by": "text", "value": "获取验证码"}],
                    "agreement":   [{"by": "left_clickable_in_row", "value": "我已阅读并同意"}],
                    # 简化版登录页（预填手机号）的"验证码登录"直入按钮（无此变体时自然解不出）
                    "quick_login": [{"by": "text", "value": "验证码登录"}],
                },
                routes=[
                    # 路径一（单跳）：首页直接有"去登录"入口（底部登录横幅等）
                    Route(hops=(
                        Hop(enter=[{"by": "text", "value": "去登录"}],
                            expect=[{"by": "text", "value": "获取验证码"}]),
                    )),
                    # 路径二（两跳）：无直达入口时，经"我的"二次进入登录页
                    Route(hops=(
                        Hop(enter=[{"by": "text", "value": "我的"}],
                            expect=[{"by": "text", "value": "去登录"}]),
                        Hop(enter=[{"by": "text", "value": "去登录"}],
                            expect=[{"by": "text", "value": "获取验证码"}]),
                    )),
                ],
            ),
            PAGE_LOGIN_CODE: PageSpec(
                name="meituan-login-code@harmony",
                identity=[{"by": "text", "value": "输入验证码"}],
                controls={
                    "code_input": [{"by": "role", "value": ["TextInput", "EditText"]},
                                   {"by": "id", "value": "edit_text_view"}],
                    # 就地重发入口：文案带倒计时（"重新获取(59s)"），故用**子串**匹配，
                    # 并按版本差异列出候选文案（顺序即优先级）。
                    "resend_code": [{"by": "text", "value": "重新获取"},
                                    {"by": "text", "value": "重新发送"},
                                    {"by": "text", "value": "重发"}],
                    # 失败态**内容**（页面报"码被拒"）：用于把"提交后卡住"归因到
                    # 「码被拒」而不是「提交超时」，进而触发就地重发换码。
                    "code_error": [{"by": "text", "value": "验证码错误"},
                                   {"by": "text", "value": "验证码已过期"},
                                   {"by": "text", "value": "验证码不正确"},
                                   {"by": "text", "value": "验证码有误"}],
                },
            ),
        }
