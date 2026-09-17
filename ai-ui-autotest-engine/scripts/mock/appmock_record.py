#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""AppMock 录制 —— 开始/停止录制、获取录制数据、噪音过滤。

录制流程：
  1. enable（设备端总开关）
  2. record start --user <mis>
  3. 用户操作 App 产生网络请求
  4. record stop
  5. record data → 获取录制数据
"""
import json
import os

from core.util.paths import RECORD_DATA_JSON
from core.util.case_utils import resolve_mis, set_current_user_mis
from core.util.json_utils import write_json_atomic, read_json
from mock.appmock_core import _YOOZ_BASE
from infra.appmock_auth import _get_cookie_or_warn
from infra.ssl_helper import get_verify_flag

# ═══════════════════════════════════════════════════════════════════
# 录制数据噪音过滤
# ═══════════════════════════════════════════════════════════════════
# ── 第一层：纯日志 / 监控 / 推送上报 ──
_RECORD_NOISE_HOSTS = {
    "h.meituan.com",                # Horn 推送
    "dyeing.adp.test.sankuai.com",  # 染色预查询
    "report.meituan.com",           # 日志上报
    "analytics.meituan.com",        # 埋点上报
    "crash.meituan.com",            # 崩溃上报
    "logan.meituan.com",            # Logan 日志
    "perf.meituan.com",             # 性能上报
    "trace.meituan.com",            # 链路追踪上报
    "sentry.sankuai.com",           # Sentry 上报
    "catfront.dianping.com",        # 点评 CAT 前端监控上报
    "catfront.51ping.com",          # 51ping CAT 前端监控上报
    "catdot.dianping.com",          # 点评 CAT 埋点上报
}
# ── 第二层：SDK 监控 / 配置下发 / 资源下载 / 安全风控等非业务请求 ──
_RECORD_NOISE_HOSTS_INFRA = {
    "dynamicf.sankuai.com",             # Espresso 前端监控 SDK 上报
    "ddapi.fe.test.sankuai.com",        # 前端动态配置下发（ddblue/cpV2）
    "msstest.sankuai.com",              # MRN Bundle 资源下载（测试环境）
    "mss.sankuai.com",                  # MRN Bundle 资源下载（正式环境）
    "api.mobile.wpt.test.sankuai.com",  # WPT 时间戳同步服务
    "api.wpt.test.sankuai.com",         # WPT AB 实验结果拉取
    "msp.meituan.com",                  # Affogato/Ristretto 安全风控
    "appsec-mobile.meituan.com",        # 移动安全检测
    "alita.waimai.meituan.com",         # Alita 运维上报
    "stable.pay.test.sankuai.com",      # 收银台预决策（非酒店业务接口）
    "group.meishi.st.sankuai.com",      # 美食时间戳同步
    "dd.meituan.com",                   # 配置下发（cpV2/checkList/dddbundle）
    "shark.dianping.com",               # Shark 长连接负载均衡
    "cs.meituan.com",                   # 安全风控设备信息
    "mtmessage.meituan.com",            # 消息 Banner 样式拉取
}
# ── 第四层：App 首页框架 / 通用能力域名（与酒店业务无关） ──
_RECORD_NOISE_HOSTS_APP = {
    # 消息 / 推送 / 红点
    "gaea.meituan.com",                 # 消息 Tab 红点 / 首页入口配置（msg/tabInfo, mop/entry/*）
    "pubmsg.meituan.com",               # 公共消息状态轮询（status/getStatus，高频）
    "assistify.meituan.com",            # Horn 推送客户端配置
    # App 首页框架 / 运营位
    "aop.meituan.com",                  # 首页布局模板 / 层级配置（getMbcTemplates, indexLayer）
    "mop.meituan.com",                  # 闪屏开屏广告（startupPicture）
    "mgc.meituan.com",                  # MGC 容器策略
    "contents.meituan.com",             # 视频容器 / 广告黑名单 / 冷启动配置
    # 首页 Feed / 二楼 / 搜索 / 推荐
    "feedguess.meituan.com",            # 首页 Feed 猜你喜欢推荐
    # 定位 / 地图
    "mars.meituan.com",                 # 定位 SDK（locate/v4/sdk/loc，高频重复）
    "api-map.meituan.com",              # 地图轮廓配置
    # 用户 / 账号 / 隐私
    "open.meituan.com",                 # 用户信息 / 封禁弹窗 / 隐私开关
    "passport.meituan.com",             # 登录态查询
    "mt-personalcenter.meituan.com",    # 个人中心状态
    # 设备 / 更新 / 时间 / 支付
    "timeservice.meituan.com",          # 时间同步服务（cappuccino）
    "recce.pay.test.sankuai.com",       # 支付插件检查（测试环境）
    "stable.pay.st.sankuai.com",        # 收银台预决策（ST 测试环境）
    "pt-api.meituan.com",              # 全局组件配置
    # 其他框架
    "kk.meituan.com",                   # WiFi 控件配置
    "web.meituan.com",                  # 小说频道等非酒店 Web 入口
    # 跨业务线 / AI 框架
    "ohhotelapi.meituan.com",           # Alita 端智能 DSL 服务（predictorServer），非业务逻辑
    "wmapi-mt.meituan.com",             # 外卖 API 域名，跨业务线配置请求（mtapi/v6/set/info）
    # GIS / 地理信息通用服务（城市查询、行政区划）
    "gw.ia.test.sankuai.com",           # GIS 测试环境（admindivision/queryMtCityByAdId, queryOpenAdInfo）
    "gw.ia.sankuai.com",                # GIS 线上环境
    # 跨业务线测试域名
    "api.c.waimai.test.sankuai.com",    # 外卖测试域名（mtapi/v6/set/info 等配置请求）
}
# ── 第三层：CDN / 图片等静态资源域名后缀（后缀匹配） ──
_RECORD_NOISE_HOST_SUFFIXES = (
    ".d.meituan.net",                   # CDN 图片（p0~p20/m0/o0.d.meituan.net）
    ".dreport.meituan.net",             # 地图/定位 SDK 快照上报
    ".meituan.net",                     # s3plus 等静态资源 / Ocean 区块配置
)

_RECORD_NOISE_URL_KEYWORDS = [
    "/hornNew",          # Horn 推送
    "/horn_ios/",        # iOS Horn 推送合并请求
    "/horn?",            # Horn 推送（不带 New 后缀）
    "/dyeing/preQuery",  # 染色预查询
    "/mtsi-worker/",     # MTSI 埋点上报
    "/fetch_tags",       # AB 标签拉取
    "/assistant/message/fetchMessage",  # 消息拉取
    "/shark/report",     # Shark 上报
    "/log/batch",        # 日志批量上报
    "/data/report",      # 数据上报
    "/config/mrn/checkList",  # MRN 配置检查
    "/api/metric",       # 前端性能/业务指标上报（高频噪声，占录制数据 ~80%）
    "/api/log",          # 前端日志上报
    "/api/pv",           # PV 页面访问上报
    "/api/event",        # 事件上报
    "/broker-service/metrictag",  # Broker 指标标签上报
    "/api/espresso",     # Espresso SDK 上报（配合 dynamicf host 双保险）
    "/api/affogato",     # Affogato 安全风控
    "/api/ristretto",    # Ristretto 安全风控
    "/abtest/",          # AB 实验结果拉取
    "/api/multi/loadbalance",  # Shark 负载均衡
    "/perf/met_",        # 性能 SDK 上报（met_babel_android 等，高频噪声）
    "/mapi/mlog/",       # 美团日志上报（mlog/mtzmidas 等）
    "/sdk/report",       # SDK 数据上报
    "/sdk/pushToStartTokenReport",  # 推送 Token 上报
    "/api/privacy/",     # 隐私合规配置/参数拉取
    "/marketing/sdk/ab/",  # 营销 SDK AB 实验
    "/mapi/networktunnel.bin",  # 网络隧道探测
    # App 首页通用接口路径关键词
    "/aggroup/",         # 首页二楼 / 频道 / Tab（secondFloor/*, indexTab, homepage/display）
    "/uuid/v2/collect",  # 设备 UUID 采集
    "/appupdate/",       # App 更新检查（alita/checkUpdate）
    "/mapi/framework/",  # 点评模块配置（modulesconfig.bin）
    "/prerender/",       # 预渲染配置（gcbupg.bin）
    "/group/v1/deal/searchpage/",  # 搜索默认词（非酒店业务）
    "/group/v1/recommend/unity/",  # 推荐 AB 实验（非酒店业务）
    "/group/v1/timestamp/",         # 时间戳同步轮询（高频，apimobile 域名）
    "/hormuz/",                     # 端智能推荐引擎（trigger/getAlitaDsl），AI 框架层
]


def _normalize_host(host: str) -> str:
    """去除端口号，统一小写：'dynamicf.sankuai.com:443' → 'dynamicf.sankuai.com'"""
    return host.lower().rsplit(":", 1)[0] if ":" in host else host.lower()


def _filter_noise_records(items: list) -> list:
    """过滤日志上报、监控、埋点、CDN 图片等无业务价值的录制数据。"""
    filtered = []
    for item in items:
        raw_host = (item.get("host") or "")
        host = _normalize_host(raw_host)
        req_url = (item.get("reqUrl") or "").lower()

        # host 黑名单（第一层：纯日志/监控）
        if host in _RECORD_NOISE_HOSTS:
            continue
        # host 黑名单（第二层：基础设施/SDK/配置/安全）
        if host in _RECORD_NOISE_HOSTS_INFRA:
            continue
        # host 黑名单（第四层：App 首页框架/通用能力）
        if host in _RECORD_NOISE_HOSTS_APP:
            continue
        # host 后缀匹配（第三层：CDN 图片/静态资源）
        if any(host.endswith(suffix) for suffix in _RECORD_NOISE_HOST_SUFFIXES):
            continue
        # URL 关键词黑名单
        if any(kw.lower() in req_url for kw in _RECORD_NOISE_URL_KEYWORDS):
            continue
        # 过滤 reqUrl 只有 "/?" 的空请求（通常是 WebSocket 升级或心跳）
        # 排除 lx0.meituan.com：灵犀埋点 SDK 的请求路径也是 "/?"，埋点事件在 body 中
        if req_url.strip() in ("/?", "/") and host != "lx0.meituan.com":
            continue
        filtered.append(item)
    return filtered


def _record_interface_key(item: dict) -> str:
    """生成接口级稳定标识：host + reqUrl（去掉 query string）。

    用于判断"同一个接口"——同一接口的多次请求（不同 timestamp/body）
    视为同一条记录，后到的覆盖先到的。
    """
    host = _normalize_host(item.get("host") or "")
    req_url = item.get("reqUrl") or ""
    # 去掉 query string，只保留 path 部分
    path = req_url.split("?")[0].split("#")[0]
    return f"{host}{path}"


def _save_record_data(result: dict, save_path: str):
    """将录制数据增量合并持久化到文件。

    服务端每次返回当前录制 session 的全量数据（但受 pageSize 限制可能截断）。
    本地采用接口级覆盖策略：以 host+path 为接口标识，同接口的新记录覆盖旧记录，
    不追加。确保同一接口只保留最新一条录制数据。
    """
    try:
        d = os.path.dirname(save_path)
        if d:
            os.makedirs(d, exist_ok=True)

        new_items = result.get("items", [])

        # 读取本地已有数据
        existing_items = []
        if os.path.isfile(save_path):
            try:
                existing = read_json(save_path, default=[])
                existing_items = existing.get("items", [])
            except (json.JSONDecodeError, KeyError):
                existing_items = []

        # 构建已有数据的接口标识索引
        existing_map = {}  # key → index in existing_items
        for i, item in enumerate(existing_items):
            key = _record_interface_key(item)
            existing_map[key] = i

        # 合并：同接口覆盖，新接口追加
        overwrite_count = 0
        append_count = 0
        for item in new_items:
            key = _record_interface_key(item)
            if key in existing_map:
                existing_items[existing_map[key]] = item
                overwrite_count += 1
            else:
                existing_map[key] = len(existing_items)
                existing_items.append(item)
                append_count += 1

        merged_result = {"items": existing_items, "hasNext": result.get("hasNext", False)}
        write_json_atomic(save_path, merged_result)

        print(f"APPMOCK RECORD DATA SAVED: {save_path} (覆盖 {overwrite_count}, 新增 {append_count}, 总计 {len(existing_items)})")
    except Exception as e:
        print(f"APPMOCK RECORD DATA SAVE ERROR: {e}")


def _extract_record_items(data: dict, max_depth: int = 5) -> dict:
    """从 AppMock 录制数据的多层嵌套中提取 items 列表。

    CLI 返回结构: {code, data: {items: [...], count, hasNext}}
    yooz 代理结构: {code, data: {code, data: {code, data: {requestDataList: [...], hasNext}}}}

    统一返回: {"items": [...], "hasNext": bool} 或 None（解析失败）
    """
    if not isinstance(data, dict):
        return None
    layer = data
    for _ in range(max_depth):
        # 找到含 requestDataList 或 items 的层
        if isinstance(layer, dict):
            if "requestDataList" in layer:
                return {"items": layer["requestDataList"], "hasNext": layer.get("hasNext", False)}
            if "items" in layer and isinstance(layer["items"], list):
                return {"items": layer["items"], "hasNext": layer.get("hasNext", False)}
            # 继续往下挖
            inner = layer.get("data")
            if isinstance(inner, dict):
                layer = inner
            else:
                break
        else:
            break
    return None


def _build_exclude_params() -> dict:
    """将本地维护的噪音黑名单组装为服务端过滤参数。

    返回 dict，包含 excludeHosts / excludeHostSuffixes / excludeUrls 三个 key，
    值为逗号分隔的字符串，直接作为 query params 传给 yooz-server。
    """
    all_hosts = (list(_RECORD_NOISE_HOSTS)
                 + list(_RECORD_NOISE_HOSTS_INFRA)
                 + list(_RECORD_NOISE_HOSTS_APP))
    return {
        "excludeHosts": ",".join(all_hosts),
        "excludeHostSuffixes": ",".join(_RECORD_NOISE_HOST_SUFFIXES),
        "excludeUrls": ",".join(_RECORD_NOISE_URL_KEYWORDS),
    }


# ═══════════════════════════════════════════════════════════════════
# 录制接口
# ═══════════════════════════════════════════════════════════════════

def appmock_record_start(filter_str: str = "",
                         add_mock: bool = False, mis: str = None) -> bool:
    """开始录制设备网络请求（直接走 yooz 代理）。

    yooz 代理调用 /appmockapi/record/startRecord，后端 API 接受 userDomain
    且不受 MULTIPLE_BOUND_DEVICES 限制，无需经过 CLI。

    Args:
        filter_str: URL 过滤词
        add_mock: 是否录制时实时写入 Mock
        mis: MIS 号（userDomain）
    """
    mis = resolve_mis(mis)
    if not mis:
        print("APPMOCK RECORD START: 需要 mis（用户 MIS 号）")
        return False
    set_current_user_mis(mis)

    import requests as _req
    try:
        body = {"filter": filter_str, "addMock": add_mock, "userDomain": mis}
        resp = _req.post(f"{_YOOZ_BASE}/record/start", json=body, timeout=15, verify=get_verify_flag())
        data = resp.json()
        inner = data.get("data", {})
        if isinstance(inner, dict) and inner.get("code") == 0:
            print(f"APPMOCK RECORD START OK: mis={mis} (接口录制已启动)")
            return True
        print(f"APPMOCK RECORD START FAIL: {data} (接口录制启动失败)")
    except Exception as e:
        print(f"APPMOCK RECORD START ERROR: {e}")
    return False


def appmock_record_stop(mis: str = None) -> bool:
    """停止录制（直接走 yooz 代理）。"""
    mis = resolve_mis(mis)
    if not mis:
        print("APPMOCK RECORD STOP: 需要 mis（用户 MIS 号）")
        return False

    import requests as _req
    try:
        resp = _req.post(
            f"{_YOOZ_BASE}/record/stop",
            json={"userDomain": mis},
            timeout=15,
            verify=get_verify_flag()
        )
        data = resp.json()
        inner = data.get("data", {})
        if isinstance(inner, dict) and inner.get("code") == 0:
            print(f"APPMOCK RECORD STOP OK: mis={mis} (接口录制已停止)")
            return True
        print(f"APPMOCK RECORD STOP FAIL: {data} (接口录制停止失败)")
    except Exception as e:
        print(f"APPMOCK RECORD STOP ERROR: {e}")
    return False


def appmock_record_data(page: int = 1, page_size: int = 100,
                        mis: str = None, auto_filter: bool = True,
                        save_path: str = RECORD_DATA_JSON,
                        exclude_noise: bool = False) -> dict:
    """获取录制数据（直接走 yooz 代理），默认自动保存到本地。

    Args:
        page: 分页页码（exclude_noise 模式下忽略，服务端自动翻页拉全量）
        page_size: 分页大小（exclude_noise 模式下忽略）
        mis: MIS 号
        auto_filter: 客户端自动过滤日志上报等无业务价值的请求（默认 True）
        save_path: 录制数据持久化文件路径（默认 .run/record_data.json，传 None 不保存）
        exclude_noise: 服务端噪音过滤（True 时将本地噪音规则传给 yooz 代理，
                       服务端自动翻页拉全量 + 按规则过滤，返回干净的业务数据）

    Returns:
        {"items": [...], "hasNext": bool}（失败返回空 dict）
    """
    mis = resolve_mis(mis)
    if not mis:
        print("APPMOCK RECORD DATA: 需要 mis（用户 MIS 号）")
        return {}

    import requests as _req

    # 获取 SSO Cookie 用于鉴权（修复未认证访问漏洞）
    sso_cookie = _get_cookie_or_warn()
    if not sso_cookie:
        print("APPMOCK RECORD DATA: SSO Cookie 获取失败，无法调用录制数据接口")
        return {}

    # 自适应分页：服务端返回全量数据（无增量 API），数据量大时容易触发网关 body length 限制
    # 策略：先用原始 page_size 尝试，遇到 "body length too long" 自动折半重试，最小到 5
    _FALLBACK_SIZES = [page_size]
    s = page_size
    while s > 10:
        s = s // 2
        _FALLBACK_SIZES.append(s)
    if _FALLBACK_SIZES[-1] > 5:
        _FALLBACK_SIZES.append(5)

    for attempt, cur_page_size in enumerate(_FALLBACK_SIZES):
        try:
            params = {"page": str(page), "pageSize": str(cur_page_size), "userDomain": mis, "ssoCookie": sso_cookie}
            if exclude_noise:
                # 将本地维护的噪音规则作为参数传给服务端，服务端只负责执行过滤
                params.update(_build_exclude_params())
            resp = _req.get(f"{_YOOZ_BASE}/record/data", params=params, timeout=30, verify=get_verify_flag())
            data = resp.json()
            result = _extract_record_items(data)
            if result is not None:
                raw_count = len(result.get("items", []))
                # 自动过滤日志上报等噪音数据
                if auto_filter and result.get("items"):
                    result["items"] = _filter_noise_records(result["items"])
                    filtered_count = raw_count - len(result["items"])
                    if filtered_count > 0:
                        print(f"APPMOCK RECORD DATA: 已过滤 {filtered_count} 条日志/监控上报")
                if attempt > 0:
                    print(f"APPMOCK RECORD DATA: 自适应降级 pageSize={cur_page_size} 成功 (第 {attempt + 1} 次尝试)")
                print(f"APPMOCK RECORD DATA OK: mis={mis}, count={len(result.get('items', []))} (原始 {raw_count})")
                # 持久化到文件（可选）
                if save_path and result.get("items"):
                    _save_record_data(result, save_path)
                return result
            # 检查是否是 body length 超限，可降级重试
            err_msg = str(data.get("errorMessage", "")) if isinstance(data, dict) else ""
            if "body length too long" in err_msg and attempt < len(_FALLBACK_SIZES) - 1:
                print(f"APPMOCK RECORD DATA: 响应体过大 (pageSize={cur_page_size})，自动缩小到 pageSize={_FALLBACK_SIZES[attempt + 1]} 重试...")
                continue
            print(f"APPMOCK RECORD DATA FAIL: {data}")
        except Exception as e:
            if attempt < len(_FALLBACK_SIZES) - 1:
                print(f"APPMOCK RECORD DATA ERROR (pageSize={cur_page_size}): {e}，自动缩小重试...")
                continue
            print(f"APPMOCK RECORD DATA ERROR: {e}")
    return {}


# ═══════════════════════════════════════════════════════════════════
# 录制数据过滤（供动态 Mock 按需查询）
# ═══════════════════════════════════════════════════════════════════

def appmock_record_data_filter(keywords: list, mis: str = None,
                                page: int = 1, page_size: int = 100) -> list:
    """从录制数据中按关键词筛选匹配的接口。

    在全程录制（record-start 不 stop）期间调用，从已录制数据中
    筛选 reqUrl / host 包含任一关键词的条目。

    Args:
        keywords: URL 关键词列表（如 ["preview", "price"]），任一匹配即命中
        mis: MIS 号
        page: 分页页码
        page_size: 分页大小

    Returns:
        匹配的 items 列表（失败或无匹配返回空列表）
    """
    data = appmock_record_data(page=page, page_size=page_size, mis=mis)
    items = data.get("items", [])
    if not items or not keywords:
        return items

    matched = []
    for item in items:
        req_url = item.get("reqUrl", "") or ""
        host = item.get("host", "") or ""
        search_text = f"{host}{req_url}".lower()
        if any(kw.lower() in search_text for kw in keywords):
            matched.append(item)

    print(f"APPMOCK RECORD FILTER: {len(matched)}/{len(items)} items matched keywords={keywords}")
    return matched
