#!/usr/bin/env python3
"""
HTTP 网关调用封装层 - skill

用于调用需要**真实登录态**（Cookie）的 ME/EB/MTA 等 HTTP 网关接口（区别于
runner.py/du_runner.py 的 Thrift/DataUnity 直调 —— 那类调用可以显式传入
PlatformOrigin 伪造身份，但部分接口的身份判断实际由网关层根据登录 Cookie
在服务端内部构造，body 中传的身份字段会被忽略甚至压根不允许传，此时必须
走真实登录 + HTTP 网关才能让服务端正确识别身份。

背景（重要教训）：
    hotel-biz-platform 的 PlatformMeGoodsFacade#updatePriceV2 曾经历过一次
    错误实现——直调 Thrift 接口时在第二个参数 PlatformOrigin 里手工拼一个
    "userType=BIZ" 或 "userType=MIS+HOTEL_BD" 来冒充商家/BD身份，但真实生产
    调用链路是「前端 HTTP 网关 → 网关根据登录 Cookie 解析身份 → 内部转换为
    PlatformOrigin → 再转发给 Thrift 方法」，Thrift 直调完全绕过了网关的身份
    解析逻辑，服务端收到的伪造 PlatformOrigin 字段不完整、不真实，导致身份
    判断落入错误分支（商家身份被误判为 BD/整商品审核，编造的 BD 账号又因
    未在权限系统中登记而完全不生效）。

    2026-08-19 已实测验证：改用 tdm-cli 真实登录换票（商家 = blogin 换
    mebsid，BD = sso 换 messoid）+ HTTP 网关直连调用 updatePriceV2，网关
    正确识别身份并成功提交改价请求（code=10000）。本模块即为该方案的通用封装。

    BD 测试账号说明（与商家身份不同）：商家登录账号按 partnerId 区分，但 BD
    是**全局固定测试身份**，不按 partnerId 绑定权限（参考 hotel-crs 自动化仓库
    LoginUtils.getBDHeaderMap() + env.properties: ME_SSO_USER=crstest /
    ME_SSO_PASSWORD=Ceshi123 / ME_SSO_CLIENT_ID=hotel_sc），已对
    partnerId=4576342 实测验证通过。

使用：
    from scripts.http_gateway import merchant_login, call_gateway, HttpGatewayError

    bsid = merchant_login(merchant_user="4574857", merchant_password="Ceshi123", service="lvyou")
    resp = call_gateway(
        host="https://me.hotel.test.sankuai.com",
        api="/api/gw/v1/product/price/updatePriceV2",
        body={...},
        headers={"logintype": "Epassport", "Cookie": f"mebsid={bsid}"},
    )
"""

import json
import subprocess
from typing import Optional


class HttpGatewayError(Exception):
    """HTTP 网关调用错误（登录失败 / 网关鉴权失败 / 业务失败）"""
    def __init__(self, message: str, code: int = -1, raw: dict = None):
        super().__init__(message)
        self.code = code
        self.raw = raw or {}


def _find_tdm_bin() -> str:
    """
    定位 tdm-cli 可执行文件。优先假设已在 PATH 中（`npm install -g @nib/tdm-cli`
    后 `tdm` 命令应可直接使用）；PATH 中找不到时给出明确的安装/环境提示。
    """
    import shutil
    tdm_path = shutil.which("tdm")
    if tdm_path:
        return tdm_path
    raise HttpGatewayError(
        "未找到 tdm 命令。请先安装：npm install -g @nib/tdm-cli --registry=http://r.npm.sankuai.com\n"
        "若已安装但仍提示未找到，请确认 npm 全局 bin 目录（`npm config get prefix`+`/bin`）已加入 PATH。"
    )


def merchant_login(
    merchant_user: str,
    merchant_password: str = "Ceshi123",
    service: str = "lvyou",
) -> str:
    """
    商家身份登录换票（B端 passport 登录，对应 LoginType.SSO_B_LOGIN），
    用 tdm-cli 的 `tdm token blogin` 换取 bsid。

    参数：
        merchant_user     - 商家登录账号，测试环境固定用 partnerId 字符串
                             （如 "4574857"），无需单独构造用户
        merchant_password - 商家登录密码，测试环境固定 "Ceshi123"
        service            - 服务名称（SSO_B_SERVICE），酒店测试环境固定 "lvyou"

    返回：bsid 字符串（用于拼 Cookie: mebsid=<bsid>）
    异常：HttpGatewayError（tdm 未安装 / 登录失败）

    ⚠️ 免密登录说明：商家侧真实业务系统是免密登录（SSO_B_NO_PW_LOGIN，只需
    userPrefix 不需要密码），但 tdm-cli 当前 `token blogin` 只支持账号密码
    方式（SSO_B_LOGIN），因此这里固定按账号密码方式调用。测试环境商家账号
    密码统一是 partnerId / Ceshi123（学城已验证），如遇到特定供应商密码不是
    Ceshi123 的情况需调用方另行确认。
    """
    tdm_bin = _find_tdm_bin()
    cmd = [
        tdm_bin, "token", "blogin",
        "-u", str(merchant_user),
        "-p", str(merchant_password),
        "-s", str(service),
        "--raw",
    ]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    bsid = (r.stdout or "").strip()
    if r.returncode != 0 or not bsid:
        raise HttpGatewayError(
            f"商家登录换票失败（tdm token blogin，user={merchant_user}）："
            f"{(r.stderr or r.stdout or '').strip()[:500]}"
        )
    return bsid


def bd_login(
    sso_user: str = "crstest",
    sso_password: str = "Ceshi123",
    client_id: Optional[str] = "hotel_sc",
    client_secret: Optional[str] = "7d53c92b32a0fc914c30e1740b3fc774",
    sso_host: Optional[str] = None,
) -> str:
    """
    BD 身份登录换票（美团员工 SSO 登录），用 tdm-cli 的 `tdm token sso`
    换取 accessToken。

    参数：
        sso_user       - BD 员工 SSO 账号（mis），默认使用全局固定测试账号
                          "crstest"（参考 hotel-crs 自动化仓库
                          LoginUtils.getBDHeaderMap() + env.properties，
                          2026-08-19 已实测验证通过）
        sso_password   - BD 员工 SSO 密码，默认 "Ceshi123"
        client_id      - SSO 客户端 ID，默认 "hotel_sc"
        client_secret  - SSO 客户端密钥，默认值见上方（对应 hotel_sc 客户端）
        sso_host       - SSO 服务地址，不传使用 tdm-cli 默认值

    返回：accessToken 字符串（用于拼 Cookie: messoid=<accessToken>）
    异常：HttpGatewayError（tdm 未安装 / 登录失败）

    ⚠️ 与商家身份不同，BD 身份是**全局固定测试账号**，不按 partnerId 绑定
    权限（默认账号 crstest 已对 partnerId=4576342 实测验证通过）。若调用方
    传入了其他 BD 账号但改价接口仍返回"商家水平鉴权失败"类错误，再考虑是否
    该账号本身权限有限制。
    """
    tdm_bin = _find_tdm_bin()
    cmd = [tdm_bin, "token", "sso", "-u", str(sso_user), "-p", str(sso_password), "--raw"]
    if client_id:
        cmd += ["--client-id", str(client_id)]
    if client_secret:
        cmd += ["--client-secret", str(client_secret)]
    if sso_host:
        cmd += ["--host", str(sso_host)]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    token = (r.stdout or "").strip()
    if r.returncode != 0 or not token:
        raise HttpGatewayError(
            f"BD登录换票失败（tdm token sso，user={sso_user}）："
            f"{(r.stderr or r.stdout or '').strip()[:500]}"
        )
    return token


def call_gateway(
    host: str,
    api: str,
    body: dict,
    headers: dict,
    http_method: str = "POST",
    timeout_s: int = 30,
    raise_on_biz_error: bool = True,
) -> dict:
    """
    直连调用 HTTP 网关接口（curl，不走任何代理）。

    参数：
        host        - 完整域名前缀，如 "https://me.hotel.test.sankuai.com"
        api         - 接口路径，如 "/api/gw/v1/product/price/updatePriceV2"
        body        - 请求体 dict，会被序列化为 JSON
        headers     - 请求头 dict，须含登录态（如 {"logintype": "Epassport",
                      "Cookie": "mebsid=<bsid>"}）
        http_method - HTTP 方法，默认 POST
        timeout_s   - 超时时间（秒）
        raise_on_biz_error - True 时业务失败（网关鉴权失败/接口报错）抛异常，
                      False 时原样返回响应 dict 供调用方自行判断

    返回：接口原始响应 dict（JSON 解析后）
    异常：HttpGatewayError（网络失败 / JSON 解析失败 / 业务失败）
    """
    url = host.rstrip("/") + api
    cmd = [
        "curl", "-s", "-X", http_method.upper(), url,
        "--max-time", str(timeout_s),
    ]
    for k, v in headers.items():
        cmd += ["-H", f"{k}: {v}"]
    if body is not None:
        cmd += ["-H", "Content-Type: application/json", "-d", json.dumps(body, ensure_ascii=False)]

    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_s + 5)
    raw_text = (r.stdout or "").strip()
    try:
        result = json.loads(raw_text)
    except json.JSONDecodeError:
        raise HttpGatewayError(f"响应非 JSON（可能网络异常）：{raw_text[:500]}")

    if raise_on_biz_error:
        _check_gateway_error(result)

    return result


def _check_gateway_error(result: dict) -> None:
    """
    检查网关/业务错误并抛出 HttpGatewayError。

    常见错误码（ME/EB 网关约定）：
        679 - 统一鉴权失败（如"商家水平鉴权失败"，通常是登录账号与目标
              partnerId/poiId 权限绑定关系不对，非登录态本身问题）
        606 - 未登录（Cookie 失效或网关未配置该接口的 authType）
        10000/0 - 成功（不同网关约定不同，需结合具体接口判断）
    """
    code = result.get("code")
    if code in (10000, 0, 200):
        return
    err = result.get("error") or {}
    msg = (err.get("msg") if isinstance(err, dict) else None) or result.get("message") or str(result)
    raise HttpGatewayError(f"网关调用失败（code={code}）：{msg}", code=code if isinstance(code, int) else -1, raw=result)

