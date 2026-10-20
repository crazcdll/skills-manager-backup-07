#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""MeituanAppDescriptor — 美团 Android App 描述符实现。

封装美团 App 的包名、首页 Activity、AppMock URI、调试控件类名、Scheme 前缀等常量。

新增其他 App（如点评）时，在同目录下新建一个文件（如 dianping.py）实现同样的
AppDescriptor 接口，并在 devices/registry.py::_APP_REGISTRY 追加一行注册，
不需要改动本文件或 shared/context.py。
"""
from devices.base import AppDescriptor


class MeituanAppDescriptor(AppDescriptor):
    """美团 App 描述符。"""

    _PACKAGE = "com.sankuai.meituan"
    _MAIN_ACTIVITY_CLASS = "com.meituan.android.pt.homepage.activity.MainActivity"

    @property
    def package_name(self) -> str:
        return self._PACKAGE

    @property
    def main_activity_class(self) -> str:
        return self._MAIN_ACTIVITY_CLASS

    @property
    def appmock_content_uri(self) -> str:
        return f"content://{self._PACKAGE}.appmock/mock"

    @property
    def debug_overlay_prefixes(self) -> tuple:
        return (
            "com.meituan.android.mrn.debug.n$c",
            f"{self._PACKAGE}.kernel.net.utils.b$a",
            "com.meituan.android.recce.debug.widget",
        )

    @property
    def scheme_prefix(self) -> str:
        return "imeituan://www.meituan.com"

    @property
    def uninspectable_activities(self) -> tuple:
        """不支持 imeituan inspect-tree 的 Activity 标识列表（小写），降级走 uiautomator。
        
        包括：首页 MainActivity（未集成 dump 能力）、升级弹窗 UpgradeDialogActivity（短期弹窗，无 dump 能力）。
        """
        return ("mainactivity", "upgradedialogactivity")

    @property
    def page_specs(self) -> dict:
        """登录页 / 验证码页描述（**数据**）。

        Android 侧特征：登录页是**独立 Activity**（窗口名含 login，可做快速标记）、
        且**暴露 resource-id** → 选择器 `id` 优先，`role`/`text` 兜底。
        """
        from devices.interfaces.page_spec import (PAGE_LOGIN, PAGE_LOGIN_CODE,
                                                 PageSpec, Route, Hop)

        return {
            PAGE_LOGIN: PageSpec(
                name="meituan-login@android",
                identity=[{"by": "text", "value": "获取短信验证码"},
                          {"by": "text", "value": "获取验证码"},
                          {"by": "text", "value": "密码登录"}],
                markers=("login",),
                controls={
                    "phone_input": [{"by": "id", "value": "passport_mobile_phone"},
                                    {"by": "role", "value": ["EditText", "TextInput"]}],
                    "send_code":   [{"by": "id", "value": "passport_mobile_next"},
                                    {"by": "text", "value": "获取短信验证码"},
                                    {"by": "text", "value": "获取验证码"}],
                    "agreement":   [{"by": "id", "value": "dynamic_checkbox"},
                                    {"by": "left_clickable_in_row", "value": "我已阅读并同意"}],
                    # 勾选**状态**来源（与"点哪里"分离）：Android 复选框暴露真实 checked
                    "agreement_state": [{"by": "id", "value": "dynamic_checkbox"}],
                    # 简化版登录页（预填手机号）的"验证码登录"直入按钮
                    "quick_login": [{"by": "text", "value": "验证码登录"}],
                },
                routes=[
                    # 路径一（单跳）：首页直接有"去登录"入口（底部登录横幅等）
                    Route(hops=(
                        Hop(enter=[{"by": "text", "value": "去登录"}],
                            expect=[{"by": "text", "value": "获取短信验证码"},
                                    {"by": "text", "value": "获取验证码"}]),
                    )),
                    # 路径二（两跳）：无直达入口时，经"我的"二次进入登录页。
                    # 「我的」页的登录入口文案随版本变过（去登录 / 点击登录），两种都收。
                    Route(hops=(
                        Hop(enter=[{"by": "text", "value": "我的"}],
                            expect=[{"by": "text", "value": "点击登录"},
                                    {"by": "text", "value": "去登录"}]),
                        Hop(enter=[{"by": "text", "value": "点击登录"},
                                   {"by": "text", "value": "去登录"}],
                            expect=[{"by": "text", "value": "获取短信验证码"},
                                    {"by": "text", "value": "获取验证码"}]),
                    )),
                ],
            ),
            PAGE_LOGIN_CODE: PageSpec(
                name="meituan-login-code@android",
                identity=[{"by": "text", "value": "输入验证码"}],
                controls={
                    "code_input": [{"by": "id", "value": "edit_text_view"},
                                   {"by": "role", "value": ["EditText", "TextInput"]}],
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
