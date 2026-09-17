#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""设备连接引导注册表 —— 环境异常场景 → 用户可执行分步指引。

与 device_validator（组合是否受支持）、env_validator（认证信息是否齐备）职责正交：
本模块负责组合合法但设备"当前不可达"时，如何指导用户现场修复。

新增引导场景只需在 GUIDANCE_REGISTRY 追加一条数据，不改探测逻辑/调用方代码。
每条引导是纯数据（标题 + 分步操作 + 重试提示），不含交互逻辑——
「展示给用户 → 确认 → 重试」的编排由 AI 在会话层完成，脚本不做等待/轮询。

探测类命令遇到"环境可能可修复"的失败时，调用 build_guidance_payload() 输出
结构化 dict 供 AI 转述指引；无法修复的问题（如工具缺失）仍走原有纯文本报错。
"""

# 引导场景注册表：key 用 "<platform>_<device_type>_<symptom>" 命名。
GUIDANCE_REGISTRY = {
    "harmony_local_not_connected": {
        "title": "未检测到已连接的鸿蒙本地真机",
        "summary": "本地真机场景需要手机通过 USB 与电脑直连，并开启开发者模式下的 USB 调试。",
        "steps": [
            "在手机上打开「设置」App",
            "进入「关于本机」，连续点击「版本号」5~7 次，直到提示「已进入开发者模式」",
            "返回「设置」→ 找到并进入「系统和更新」→「开发人员选项」（部分机型直接在「设置」根目录下）",
            "开启「USB 调试」开关",
            "使用数据线将手机连接到电脑",
            "手机屏幕会弹出授权提示，点击「允许」/「信任此设备」（勾选『始终允许』可避免每次重新授权）",
            "若电脑侧也弹出信任提示，一并确认",
        ],
        "retry_cmd": "python3 scripts/cli.py device create",
        "retry_note": "完成以上步骤后，重新执行 device create 会自动重新探测已连接设备，无需其他操作。",
    },
    "harmony_local_multiple_devices": {
        "title": "探测到多台鸿蒙本地真机",
        "summary": "本地真机场景要求唯一在线设备，避免误连接他人设备。",
        "steps": [
            "拔掉其余不需要用于本次测试的鸿蒙设备数据线，只保留一台目标设备连接",
            "或在目标设备之外的机器上执行 `hdc kill` / 断开对应设备的 USB 调试授权",
        ],
        "retry_cmd": "python3 scripts/cli.py device create",
        "retry_note": "只保留一台设备在线后，重新执行 device create 即可。",
    },
    "harmony_local_screen_locked": {
        "title": "鸿蒙本地真机当前处于熄屏/锁屏状态",
        "summary": (
            "设备已成功连接，但屏幕处于熄屏或锁屏保护态。hdc shell 通道不受屏幕状态影响，"
            "所以连接探测能通过；但后续 UI 步骤依赖“当前可见界面”，锁屏下 tap/视图树采集会"
            "静默命中锁屏/桌面而非目标 App，本地真机无人值守也无法程序化解锁，需要现在手动解锁。"
        ),
        "steps": [
            "拿起手机，按电源键或轻触屏幕唤醒",
            "完成解锁（密码/指纹/面容等），进入桌面或任意 App 前台界面",
            "解锁后请保持屏幕常亮（可在设置中调整自动锁屏时长，避免测试过程中再次熄屏）",
        ],
        "retry_cmd": "python3 scripts/cli.py device create",
        "retry_note": "解锁后重新执行 device create 会自动重新探测连接与屏幕状态，无需其他操作。",
    },
    "harmony_local_untrusted_app": {
        "title": "⚠️ 美团（企业应用）尚未获得系统信任，无法直接打开",
        "summary": (
            "设备刚完成可测性测试包的全新安装（此前设备上没有该 App），HarmonyOS 对企业签名"
            "应用有强制信任校验，首次点击图标时系统会弹出「无法打开美团，企业应用美团未经你的"
            "允许，不可运行」的拦截弹窗——这是系统级安全机制，无法通过 hdc/程序化手段绕过，必须"
            "由用户在设备上手动完成一次信任授权，且需要手动完成登录后自动化测试流程才能继续。"
        ),
        "steps": [
            "如果拦截弹窗仍在屏幕上，点击弹窗中的「去设置」；如果弹窗已消失，手动进入"
            "「设置」→「通用」（或「设置」→「应用管理」，视机型而定）→"
            "「描述文件与设备管理」/「企业应用管理」",
            "找到「美团」对应的企业应用信任项，点击进入",
            "点击「信任『美团』」/「允许」，确认信任该企业应用",
            "返回桌面，重新点击美团图标打开 App",
            "在美团登录页手动完成登录（本地真机场景固定走已登录策略 env.type=D，"
            "不会自动推送登录 scheme，需要用户在设备上自行输入账号完成登录）",
        ],
        "retry_cmd": "python3 scripts/cli.py env-prepare --env noop",
        "retry_note": (
            "完成信任授权 + 手动登录后，重新执行 env-prepare 校验登录态；"
            "若仍提示未登录，说明登录尚未完成，需要用户在设备上继续完成登录操作，不是环境故障。"
        ),
    },
    "android_local_not_connected": {
        "title": "未检测到已连接的 Android 本地真机",
        "summary": "本地真机场景需要手机通过 USB 与电脑直连，并开启开发者模式下的 USB 调试。",
        "steps": [
            "在手机上打开「设置」App",
            "进入「关于手机」，连续点击「版本号」5~7 次，直到提示「已进入开发者模式」",
            "返回「设置」→ 找到并进入「系统和更新」→「开发人员选项」",
            "开启「USB 调试」开关",
            "（华为手机专属）关闭「监控 ADB 安装应用」开关，否则安装测试包会弹拦截",
            "（华为手机专属）退出「纯净模式」（设置 → 系统和更新 → 纯净模式 → 退出）",
            "使用数据线将手机连接到电脑",
            "手机屏幕会弹出授权提示，点击「允许」/「信任此设备」（勾选『始终允许』可避免每次重新授权）",
            "下拉通知栏，将 USB 连接方式切换为「传输文件 / MTP」",
        ],
        "retry_cmd": "python3 scripts/cli.py device create",
        "retry_note": "完成以上步骤后，重新执行 device create 会自动重新探测已连接设备，无需其他操作。",
    },
    "android_local_multiple_devices": {
        "title": "探测到多台 Android 本地真机",
        "summary": "本地真机场景要求唯一在线设备，避免误连接他人设备。",
        "steps": [
            "拔掉其余不需要用于本次测试的 Android 设备数据线，只保留一台目标设备连接",
            "或在目标设备之外的机器上执行 `adb kill-server` 断开对应设备的连接",
        ],
        "retry_cmd": "python3 scripts/cli.py device create",
        "retry_note": "只保留一台设备在线后，重新执行 device create 即可。",
    },
    "android_local_screen_locked": {
        "title": "Android 本地真机当前处于熄屏/锁屏状态",
        "summary": (
            "设备已成功连接，但屏幕处于熄屏或锁屏保护态。adb shell 通道不受屏幕状态影响，"
            "所以连接探测能通过；但后续 UI 步骤依赖「当前可见界面」，锁屏下 tap/视图树采集会"
            "静默命中锁屏/桌面而非目标 App，需要现在手动解锁。"
        ),
        "steps": [
            "拿起手机，按电源键或轻触屏幕唤醒",
            "完成解锁（密码/指纹/面容等），进入桌面或任意 App 前台界面",
            "解锁后请保持屏幕常亮（可在开发者选项中开启「屏幕常亮」开关，避免测试过程中再次熄屏）",
        ],
        "retry_cmd": "python3 scripts/cli.py device create",
        "retry_note": "解锁后重新执行 device create 会自动重新探测连接与屏幕状态，无需其他操作。",
    },
    "ios_simulator_xcode_not_installed": {
        "title": "未检测到 Xcode 或 xcrun 工具链",
        "summary": "本地 iOS 模拟器环境依赖 macOS 原生 Xcode 和 Command Line Tools。",
        "steps": [
            "打开 App Store 搜索并安装 Xcode，或访问 Apple Developer 官网下载",
            "在终端执行 `sudo xcode-select -s /Applications/Xcode.app` 确认开发者路径",
            "在 Xcode 中打开 Settings → Platforms，下载对应的 iOS Simulator Runtime",
        ],
        "retry_cmd": "python3 scripts/cli.py device create",
        "retry_note": "Xcode 配置完成后，重新执行 device create 即可自动识别。",
    },
    "ios_simulator_no_booted_device": {
        "title": "未找到或无法自动启动 iOS 模拟器",
        "summary": "本地缺少可用的 iOS 模拟器实例或模拟器启动超时。",
        "steps": [
            "在终端执行 `imeituan device simulator list` 查看已安装的模拟器列表",
            "如无实例，可执行 `imeituan device simulator quick-start -p ios` 自动创建并启动",
            "或手动在 Simulator App 中启动一个 iPhone 实例",
        ],
        "retry_cmd": "python3 scripts/cli.py device create",
        "retry_note": "模拟器启动进入桌面后，重新执行 device create 即可。",
    },
}


def get_guidance(guidance_id):
    """按 id 查询引导数据，未注册时返回 None（调用方应回退到原有纯文本报错）。"""
    return GUIDANCE_REGISTRY.get(guidance_id)


def build_guidance_payload(guidance_id, *, detail=None, extra=None):
    """构造结构化引导输出，供探测类命令在失败时通过 stdout 返回给 AI。

    Args:
        guidance_id: GUIDANCE_REGISTRY 中的 key。
        detail: 本次探测的原始上下文信息（如 platform、已探测到的序列号列表），
            用于 AI 判断/展示，不影响引导步骤本身。
        extra: 额外补充字段（预留扩展位，如未来需要附加截图路径等）。

    Returns:
        dict，形如 {"ok": False, "guidance": {...}}；guidance_id 未注册时返回
        None，调用方应回退到原有的 _emit_err 纯文本报错，不静默吞掉错误。
    """
    guidance = get_guidance(guidance_id)
    if guidance is None:
        return None

    payload = {
        "ok": False,
        "recoverable": True,
        "guidance": {
            "guidance_id": guidance_id,
            "title": guidance["title"],
            "summary": guidance["summary"],
            "steps": guidance["steps"],
            "retry_cmd": guidance["retry_cmd"],
            "retry_note": guidance["retry_note"],
        },
        "ai_hint": (
            "请将 guidance.steps 按顺序转述给用户（用户可读的分步操作指引），"
            "引导完成后通过 AskQuestion 询问用户是否已处理完毕/是否重试；"
            "用户确认后重新执行 guidance.retry_cmd 重试探测，不要直接判定流程失败终止。"
        ),
    }
    if detail is not None:
        payload["detail"] = detail
    if extra:
        payload["guidance"].update(extra)
    return payload
