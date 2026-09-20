#!/usr/bin/env python3
"""
接口层：闲置房充值（子产品生产）

工具：闲置房充值（HTTP 直连 EB 网关）
url：POST http://eb.hotel.test.sankuai.com/api/v1/ebooking/vacantHouse/rechargeV2
鉴权：Cookie `ebbsid=<bsid>`，bsid 通过 tdm-cli 免密登录换取：
       tdm token blogin --skip-password -u <商家账号登录名> --raw

⚠️ 为什么走 HTTP 而不是 Thrift（2026-09-16 实测结论）：
  底层 Thrift 方法 `EbPcGoodsFacade#batchRechargeFreeHouse` 在 DataUnity 网关上
  无法路由（`connection list is empty`）；研发日常也是直接调 EB 后台 HTTP 接口。
  因此本接口层用 tdm-cli 在客户端完成免密登录换票，再 curl 直连 HTTP 网关。

⚠️ 闲置房是"子产品"，必须依赖一个已上线的**母产品**（境内全日房，见 W1）才能生产：
   rechargeGoods[].goodsId 即母产品（全日房）的 goodsId。

⚠️ 资金池前置（2026-09-16 实测踩坑，假成功根因）：
  充值流程第一步是资金池检查（containsCoinPool_check），若商家账号未开通资金池，
  接口会**静默跳过充值但外层仍返回 {"status":0,"message":"成功","data":null}**（假成功）。
  使用前必须确保商家已开资金池：
    mt-testdata hotel coinpool --action open --merchant-type hotel-yf \
      --biz-account-id <商家账号ID> --partner-id <partnerId>
  判别真假成功：真实成功返回 `data:true`；`data:null` 大概率是资金池检查未通过。

⚠️ rechargeScheme（充值方案）：
  - 0 = 先充值：需要 Moka 平台配置「免费房估值信息」mock，否则报"查不到免费房估值信息"
  - 1 = 先售卖（默认）：不需要估值 mock，推荐默认使用

因此本接口层只需要：
  1. 根据 partnerId 查询该供应商关联的商家账号登录名（使用 merchant-testdata-cli，命令名 `merchant-testdata-cli`）：
       merchant-testdata-cli hotel account --action query-partner --partner-id <partnerId>
     取返回的 loginName/login 作为 tdm-cli 免密登录的账号。
  2. tdm-cli 换 bsid → curl 直连 rechargeV2（body 中保留 "user" 字段，与 EB 前端真实请求一致）。
  3. 调用后用 mcoin 的 IFreeRoomRecordService.countByParam 验证置换记录数（Thrift，走 scripts/runner.py）。
"""

import json
import os
import subprocess
import sys
import time
from typing import Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from scripts.runner import invoke, InvokeError  # noqa

RECHARGE_URL = "http://eb.hotel.test.sankuai.com/api/v1/ebooking/vacantHouse/rechargeV2"

# 验证用：mcoin 闲置房置换记录服务（Thrift，走 scripts/runner.py invoke）
MCOIN_APPKEY = "com.sankuai.mpht.mcoin.biz"
MCOIN_SERVICE = "com.sankuai.mpht.mcoin.biz.api.freeroom.IFreeRoomRecordService"
MCOIN_METHOD = "countByParam"


class FreeRoomError(Exception):
    """闲置房调用链路错误（账号查询 / RPC 调用）"""
    def __init__(self, message: str, detail: Optional[dict] = None):
        super().__init__(message)
        self.detail = detail or {}


def _run(cmd: list, timeout: int = 30) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


# ════════════════════════════════════════════════════════════════════════════
# Step 1：按 partnerId 查询商家账号（merchant-testdata-cli，命令名 merchant-testdata-cli）
# ════════════════════════════════════════════════════════════════════════════

def query_merchant_account(partner_id: str) -> dict:
    """
    根据供应商 partnerId 查询关联的商家账号（登录名 + mid）。

    对应命令：
        merchant-testdata-cli hotel account --action query-partner --partner-id <partnerId>

    返回：{"login_name": str, "mid": str}（mid = accountId = bizAccountId）

    若该 partnerId 未查到关联账号，或账号未录入"测试账号管理平台"，
    需先执行 `merchant-testdata-cli hotel account --action add --partner-id <partnerId>` 录入后重试。
    """
    cmd = [
        "merchant-testdata-cli", "hotel", "account",
        "--action", "query-partner",
        "--partner-id", str(partner_id),
    ]
    r = _run(cmd)
    if r.returncode != 0:
        raise FreeRoomError(
            f"merchant-testdata-cli 查询账号失败（partnerId={partner_id}）: {r.stderr.strip() or r.stdout.strip()}",
            detail={"cmd": " ".join(cmd), "stdout": r.stdout, "stderr": r.stderr},
        )

    login_name, mid = _parse_query_partner_output(r.stdout)
    if not login_name:
        raise FreeRoomError(
            f"未查到 partnerId={partner_id} 关联的商家账号，原始输出：\n{r.stdout}",
            detail={"cmd": " ".join(cmd), "stdout": r.stdout},
        )
    return {"login_name": login_name, "mid": mid}


def _parse_query_partner_output(stdout: str) -> tuple:
    """
    从 merchant-testdata-cli 输出中解析 loginName/login 和 mid/accountId。

    实测（2026-08）该 CLI 的 query-partner 输出为文本格式（非纯 JSON），典型片段：
        [partnerId 快速查询] 工具 844，partnerId=4573591
          ✓ login=4573591  mid=149743805
        ════════════════════════════
          partnerId 查询完成
        ════════════════════════════
          login : 4573591
          mid   : 149743805

    解析策略：优先用正则在全文范围内精确匹配 `login[ ]*[:=][ ]*<value>` 和
    `mid[ ]*[:=][ ]*<value>`（大小写不敏感，`\\b` 词边界避免 "login" 误命中 "loginname" 内部），
    避免同一行内多个 key=value 时的错误切分；找不到时兜底尝试 JSON 解析（未来 CLI 若改纯 JSON 输出仍兼容）。
    """
    import re
    stdout = (stdout or "").strip()

    login_name, mid = None, None

    # 优先：全文正则精确匹配 key=value / key: value（避免同一行多字段被错误整行切分）
    m = re.search(r'\blogin(?:Name)?\s*[:=]\s*([^\s,，;；]+)', stdout, re.IGNORECASE)
    if m:
        login_name = m.group(1).strip('"\'')
    m = re.search(r'\bmid\s*[:=]\s*([^\s,，;；]+)', stdout, re.IGNORECASE)
    if m:
        mid = m.group(1).strip('"\'')
    if not mid:
        m = re.search(r'\b(?:accountId|bizAccountId)\s*[:=]\s*([^\s,，;；]+)', stdout, re.IGNORECASE)
        if m:
            mid = m.group(1).strip('"\'')

    if login_name:
        return login_name, mid

    # 兜底：尝试 JSON 解析（若 CLI 未来改为纯 JSON 输出）
    try:
        data = json.loads(stdout)
        if isinstance(data, dict):
            login_name = data.get("loginName") or data.get("login") or data.get("loginname")
            mid = mid or data.get("mid") or data.get("accountId") or data.get("bizAccountId")
            if login_name:
                return str(login_name), str(mid) if mid is not None else None
        if isinstance(data, list) and data:
            first = data[0]
            login_name = first.get("loginName") or first.get("login")
            mid = mid or first.get("mid") or first.get("accountId") or first.get("bizAccountId")
            if login_name:
                return str(login_name), str(mid) if mid is not None else None
    except (json.JSONDecodeError, AttributeError, TypeError):
        pass

    return login_name, mid


def ensure_account_registered(partner_id: str) -> None:
    """
    若 query-partner 查到的账号未录入"测试账号管理平台"，执行录入。
    对应命令：merchant-testdata-cli hotel account --action add --partner-id <partnerId>
    """
    cmd = [
        "merchant-testdata-cli", "hotel", "account",
        "--action", "add",
        "--partner-id", str(partner_id),
    ]
    r = _run(cmd)
    if r.returncode != 0:
        raise FreeRoomError(
            f"merchant-testdata-cli 录入账号失败（partnerId={partner_id}）: {r.stderr.strip() or r.stdout.strip()}",
            detail={"cmd": " ".join(cmd), "stdout": r.stdout, "stderr": r.stderr},
        )


# ════════════════════════════════════════════════════════════════════════════
# Step 2：调用 rechargeV2（HTTP 直连 EB 网关）
# ════════════════════════════════════════════════════════════════════════════

def _get_eb_bsid(login_name: str) -> str:
    """
    用 tdm-cli 对商家账号做免密登录（SSO_B_NO_PW_LOGIN），返回 eb bsid。

    命令：tdm token blogin --skip-password -u <login_name> --raw
    登录过程输出走 stderr，bsid 在 stdout（取最后一行非空内容兜底）。
    """
    cmd = ["tdm", "token", "blogin", "--skip-password", "-u", str(login_name), "--raw"]
    try:
        r = _run(cmd, timeout=60)
    except FileNotFoundError:
        raise FreeRoomError(
            "未找到 tdm 命令（tdm-cli 未安装或未加入 PATH），无法完成商家免密登录换票",
            detail={"cmd": " ".join(cmd)},
        )
    if r.returncode != 0:
        raise FreeRoomError(
            f"tdm-cli 免密登录失败（user={login_name}）: {r.stderr.strip() or r.stdout.strip()}",
            detail={"cmd": " ".join(cmd), "stdout": r.stdout, "stderr": r.stderr},
        )
    lines = [l.strip() for l in (r.stdout or "").splitlines() if l.strip()]
    if not lines:
        raise FreeRoomError(
            f"tdm-cli 免密登录未返回 bsid（user={login_name}），stdout 为空，stderr：{r.stderr.strip()}",
            detail={"cmd": " ".join(cmd), "stderr": r.stderr},
        )
    return lines[-1]


def call_recharge_free_room(
    body: dict,
    login_name: Optional[str] = None,
    partner_id: Optional[str] = None,
    swimlane: str = "",
    dry_run: bool = False,
) -> dict:
    """
    调用闲置房充值接口（子产品生产），HTTP 直连 EB 网关 rechargeV2。

    参数：
        body        - 完整业务入参（poiId/partnerId/customerId/rechargeGoods 等，不含 user 字段）
        login_name  - 已知商家账号登录名时可直接传入，跳过账号查询
        partner_id  - 未传 login_name 时，用 partner_id 走 query_merchant_account 自动查询
        swimlane    - 泳道（非空时给请求加 `swimlane: <泳道>` header，泳道上下文随调用链透传，
                  用于命中泳道内 Moka mock，如先充值场景的估值 mock）
        dry_run     - True 时仅打印将要发送的请求，不实际调用

    返回：接口响应 dict（原始 JSON，如 {"data":true,"status":0,"message":"成功",...}）

    真假成功判别（2026-09-16 实测）：
        - 真实成功：data == true（子产品已创建，置换记录已落库）
        - 假成功：  data == null 且 message == "成功"，大概率是资金池未开通
                    （containsCoinPool_check 静默跳过充值），需先给商家开资金池
    """
    if not login_name and not partner_id:
        partner_id = body.get("partnerId")

    if dry_run:
        print(f"\n[dry-run] 商家账号 user = {login_name or '(未提供，实际执行时将按 partnerId=%s 自动查询)' % partner_id}")
        print(f"[dry-run] HTTP 调用：POST {RECHARGE_URL}（Cookie: ebbsid=<tdm-cli blogin 获取>）")
        preview_body = dict(body)
        preview_body["user"] = login_name or "<自动查询>"
        print(f"[dry-run] request = {json.dumps(preview_body, ensure_ascii=False, indent=2)}")
        return {"dry_run": True}

    if not login_name:
        if not partner_id:
            raise FreeRoomError("login_name 和 partner_id 均未提供，无法确定商家账号")
        account = query_merchant_account(str(partner_id))
        login_name = account["login_name"]

    bsid = _get_eb_bsid(login_name)

    request = dict(body)
    request["user"] = str(login_name)

    cmd = [
        "curl", "-s", "-X", "POST", RECHARGE_URL,
        "-H", "Content-Type: application/json",
        "-H", "Accept: application/json",
        "-H", f"Cookie: ebbsid={bsid}",
    ]
    # 泳道隔离（2026-09-16 实测）：泳道上下文经 EB 网关沿调用链透传（EB→platform→mcoin），
    # mcoin 在对应泳道的部署会命中该泳道的 Moka mock（如先充值估值 mock）
    if swimlane:
        cmd += ["-H", f"swimlane: {swimlane}"]
    cmd += ["-d", json.dumps(request, ensure_ascii=False, separators=(",", ":"))]
    r = _run(cmd, timeout=60)
    if r.returncode != 0:
        raise FreeRoomError(
            f"闲置房充值 HTTP 调用失败（curl exit={r.returncode}）: {r.stderr.strip()}",
            detail={"stderr": r.stderr},
        )
    try:
        resp = json.loads(r.stdout)
    except json.JSONDecodeError:
        raise FreeRoomError(
            f"闲置房充值响应非 JSON（可能登录态失效或网关异常）: {r.stdout[:500]}",
            detail={"stdout": r.stdout[:2000]},
        )

    # 假成功检测：status=0 但 data 为 null，典型原因是商家未开通资金池被静默跳过
    if resp.get("status") == 0 and resp.get("data") is None:
        raise FreeRoomError(
            "接口返回「成功」但 data=null（假成功）：充值大概率被资金池检查静默跳过。"
            "请先给商家开通资金池：mt-testdata hotel coinpool --action open "
            f"--merchant-type hotel-yf --biz-account-id <商家账号ID> --partner-id {partner_id or body.get('partnerId')}，"
            "然后重试",
            detail={"response": resp},
        )

    return resp


def count_free_room_records(poi_id: str, partner_id: str, swimlane: str = "") -> Optional[int]:
    """
    验证用：按 partnerId + poiId 统计闲置房置换记录数（mcoin IFreeRoomRecordService.countByParam）。

    返回记录数（int）；查询失败时返回 None 并打印告警（不阻断主流程）。
    """
    try:
        resp = invoke(
            appkey=MCOIN_APPKEY,
            service=MCOIN_SERVICE,
            method=MCOIN_METHOD,
            params={"poiId": int(poi_id), "partnerId": int(partner_id)},
            swimlane=swimlane,
            timeout_ms=30000,
            dry_run=False,
            raise_on_biz_error=False,
            progress_hint="验证闲置房置换记录（countByParam）...",
        )
    except Exception as e:
        print(f"[WARN] 置换记录查询异常（不影响充值结果）: {e}", file=sys.stderr)
        return None

    # resp 结构：{"data": {"data": "{...json字符串...}"}, ...}，内层 data 为 JSON 字符串
    try:
        inner = resp
        if isinstance(inner, dict) and isinstance(inner.get("data"), dict):
            inner = inner["data"].get("data", inner)
        if isinstance(inner, str):
            inner = json.loads(inner)
        if isinstance(inner, dict) and inner.get("status") == 0:
            return int(inner.get("data") or 0)
    except Exception:
        pass
    print(f"[WARN] 置换记录查询响应解析失败: {json.dumps(resp, ensure_ascii=False)[:300]}", file=sys.stderr)
    return None


def build_recharge_body(
    poi_id: str,
    partner_id: str,
    customer_id: str,
    goods_id: str,
    goods_name: str,
    start_time_days: int = 0,
    end_time_days: int = 365,
    no_sell_rule: str = "5,6,7",
    auto_re_purchase: bool = False,
    recharge_scheme: int = 1,
    min_num: int = 3,
    max_num: int = 20,
    free_room_num: int = 10,
    simple_value: int = 10000,
    total_value: int = 100000,
    pre_goods_id: str = "",
    unable_date: Optional[list] = None,
    sale_on_holidays: int = 1,
    daily_sale_threshold: int = -1,
) -> dict:
    """
    组装闲置房充值完整请求体（不含 "user" 字段，"user" 由 call_recharge_free_room 自动补齐）。

    时间字段说明：
        startTime/endTime 为毫秒时间戳，`$+0 day` 表示今天 0 点，`$+365 day` 表示今天+365天，
        本函数直接按当前时间计算并输出真实毫秒时间戳（不再依赖 "$+N day||Timestamp" 占位符语法）。

    goods_id 必须是已成功上线的**母产品**（境内全日房）的 goodsId（见 W1）。
    """
    now = int(time.time())
    day_seconds = 86400
    start_time = (now // day_seconds) * day_seconds * 1000 + start_time_days * day_seconds * 1000
    end_time = (now // day_seconds) * day_seconds * 1000 + end_time_days * day_seconds * 1000

    return {
        "poiId": int(poi_id),
        "partnerId": int(partner_id),
        "customerId": int(customer_id),
        "startTime": start_time,
        "endTime": end_time,
        "noSellRule": no_sell_rule,
        "autoRePurchase": auto_re_purchase,
        "rechargeScheme": recharge_scheme,
        "rechargeGoods": [
            {
                "goodsId": int(goods_id),
                "goodsName": goods_name,
                "preGoodsId": pre_goods_id,
                "min": min_num,
                "max": max_num,
                "freeRoomNum": free_room_num,
                "simpleValue": simple_value,
                "totalValue": total_value,
            }
        ],
        "unableDate": unable_date or [],
        "saleOnHolidays": sale_on_holidays,
        "dailySaleThresHold": daily_sale_threshold,
    }

