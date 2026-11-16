#!/usr/bin/env python3
"""
RPC 调用封装层 - skill

使用 mt-qa-tool 的 du_thrift 模块调用 Thrift RPC 接口。

安装：
    pip install --upgrade mt-qa-tool -i http://pypi.sankuai.com/simple --trusted-host pypi.sankuai.com

使用：
    from scripts.runner import invoke, InvokeError
    result = invoke(
        appkey="com.sankuai.hotel.biz.platform",
        service="com.meituan.hotel.biz.platform.goods.facade.standard.MeGoodsFacade",
        method="batchCreateGoods",
        params={"poiId": 123, "partnerId": 456, ...},
        swimlane="",
        timeout_ms=120000,
    )
"""

import json
import sys
import time
from typing import Optional


class InvokeError(Exception):
    """RPC 调用业务错误（非网络异常）"""
    def __init__(self, message: str, code: int = -1, raw: dict = None):
        super().__init__(message)
        self.code = code
        self.raw = raw or {}


class StepError(Exception):
    """步骤执行错误（infra 流程中某一步失败）"""
    def __init__(self, step: str, reason: str, detail: dict = None):
        super().__init__(f"[{step}] {reason}")
        self.step = step
        self.reason = reason
        self.resp = detail or {}


def invoke(
    appkey: str,
    service: str,
    method: str,
    params = None,           # dict（命名参数 body 模式）
    swimlane: str = "",
    timeout_ms: int = 60000,
    dry_run: bool = False,
    raise_on_biz_error: bool = True,
    progress_hint: str = "",
    parameter_values: Optional[list] = None,   # 位置参数模式（与 params 二选一）
    parameter_types: Optional[list] = None,    # 可选，配合 parameter_values 使用
) -> dict:
    """
    调用 Thrift RPC 接口。

    参数：
        appkey          - 服务 appkey
        service         - 服务全限定类名
        method          - 方法名
        params          - 请求参数（dict），会自动 JSON 序列化
        swimlane        - 泳道（空字符串=主干）
        timeout_ms      - 超时（毫秒，默认60秒）
        dry_run         - True 时只打印不执行
        raise_on_biz_error - True 时业务错误抛出 InvokeError
        progress_hint   - 进度提示文字

    返回：接口响应 dict

    异常：
        InvokeError - 业务逻辑错误（如参数校验失败）
        RuntimeError - SDK 未安装
        Exception   - 网络/超时错误
    """
    if progress_hint:
        print(f"⏳ {progress_hint}", flush=True)

    if dry_run:
        print("\n[dry-run] 将调用以下 RPC：")
        print(f"  appkey  : {appkey}")
        print(f"  service : {service}")
        print(f"  method  : {method}")
        print(f"  swimlane: {swimlane or '主干'}")
        if parameter_values is not None:
            print(f"  parameterValues: {parameter_values}")
            if parameter_types:
                print(f"  parameterTypes : {parameter_types}")
        else:
            print(f"  params  :\n{json.dumps(params, ensure_ascii=False, indent=2)}")
        return {"dry_run": True}

    # 尝试导入 mt-qa-tool SDK
    try:
        from meituan.cli.commands.du_thrift import invoke_thrift
    except ImportError:
        raise RuntimeError(
            "mt-qa-tool 未安装，请运行：\n"
            "python3 -m pip install --upgrade mt-qa-tool "
            "-i http://pypi.sankuai.com/simple --trusted-host pypi.sankuai.com"
        )

    # 获取操作人 MIS（兼容：直接运行 scripts/ 和 pypi 包两种模式）
    try:
        from hotel_testdata_cli.scripts.utils import get_operator
        operator_mis = get_operator()
    except ImportError:
        try:
            from scripts.utils import get_operator  # noqa
            operator_mis = get_operator()
        except Exception:
            operator_mis = ""

    # 构造 meUser trace_context（@Login4Me 切面从 Mtrace 上下文读取 meUser）
    # 结构来自 UserUtil.MeUser，userType="MIS" 表示内部员工身份
    # userId 必须是美团内部员工 userId（非 bizAccountId）
    me_user_json = json.dumps({
        "userId":   53527486,
        "userType": "MIS",
        "login":    "zhaoshichuan",
        "name":     "赵世川",
        "aclBdId":  None,
    })

    # 构建调用参数（对齐 du_thrift.invoke_thrift 的参数名）
    try:
        start = time.time()
        raw_result = invoke_thrift(
            remote_appkey=appkey,
            service_name=service,
            method=method,
            body=params if parameter_values is None else None,
            parameter_values=parameter_values,
            parameter_types=parameter_types,
            timeout_ms=timeout_ms,
            swimlane=swimlane or "",
            operator=operator_mis,
            trace_context={"meUser": me_user_json},
        )
        elapsed = time.time() - start
        print(f"✅ RPC 调用完成（耗时 {elapsed:.1f}s）")
        print(f"[RPC 原始返回]\n{json.dumps(raw_result if isinstance(raw_result, (dict, list)) else {'raw': raw_result}, ensure_ascii=False, indent=2)}")
    except Exception as e:
        print(f"❌ RPC 调用异常: {e}", file=sys.stderr)
        raise

    # 解析结果
    # DataUnity 外层固定格式：{"code":200,"data":"<业务JSON字符串>","success":true}
    # 需要对 data 字段做二次 JSON 解析，取出真正的业务响应
    if isinstance(raw_result, str):
        try:
            result = json.loads(raw_result)
        except json.JSONDecodeError:
            result = {"raw": raw_result}
    elif isinstance(raw_result, dict):
        result = raw_result
    else:
        result = {"data": raw_result}

    # DataUnity 把业务响应包在 data 字段（字符串形式），二次解析
    if isinstance(result.get("data"), str) and result.get("success") is True:
        try:
            inner = json.loads(result["data"])
            if isinstance(inner, dict):
                result = inner
        except (json.JSONDecodeError, TypeError):
            pass

    # 业务错误检查
    if raise_on_biz_error:
        _check_biz_error(result)

    return result


def _check_biz_error(result: dict) -> None:
    """
    检查业务错误，抛出 InvokeError。

    判断逻辑（优先级从高到低）：
      1. success=True  → 直接放行（忽略 code 值）
      2. success=False → 直接报错（无论 code 值）
      3. success 字段不存在 → 仅看 code==0 时放行
      4. code 字段也不存在 → 无法判断时放行（允许上游调用链处理）

    注意：code=0 与 success=True 是两套不同协议，不能混用 or 逻辑：
      - DataUnity 外层返回 {success: true, code: 200}
      - 业务接口内层可能返回 {code: 0, message: ""}
      - 若 success=False 但 code=0，应视为错误（业务层面失败）
    """
    has_success = "success" in result
    has_code    = "code" in result

    if has_success:
        if result["success"] is True:
            return
        # success 存在但不是 True（False 或 None）→ 业务失败
    elif has_code:
        # 无 success 字段时才用 code 兜底
        if result["code"] == 0:
            return
    else:
        # 两个字段都没有，无法判断，放行（由调用方检查 data 字段）
        return

    # 提取错误信息
    msg = (
        result.get("message")
        or result.get("msg")
        or result.get("error")
        or str(result)
    )
    code = result.get("code") or result.get("errorCode") or -1

    # 检查 checkerResultItems（酒店平台常见校验结果格式）
    checker_items = result.get("checkerResultItems")
    if not checker_items and isinstance(result.get("data"), list):
        checker_items = result["data"]
    if isinstance(checker_items, list) and checker_items:
        checker_msgs = [
            item.get("message", "")
            for item in checker_items
            if isinstance(item, dict) and item.get("message")
        ]
        if checker_msgs:
            msg = f"{msg}; 校验详情: {'; '.join(checker_msgs)}"

    raise InvokeError(msg, code=int(code) if code is not None else -1, raw=result)


def poll_until_ready(
    check_fn,
    max_retries: int = 12,
    interval_sec: int = 10,
    desc: str = "等待就绪",
) -> bool:
    """
    轮询等待，直到 check_fn 返回 True 或达到最大重试次数。

    参数：
        check_fn    - 检查函数，返回 True 表示就绪
        max_retries - 最大重试次数（默认12次）
        interval_sec - 每次间隔秒数（默认10秒）
        desc        - 等待描述

    返回：True=就绪，False=超时
    """
    for i in range(max_retries):
        try:
            if check_fn():
                print(f"✅ {desc}（第{i+1}次检查通过）")
                return True
        except Exception as e:
            print(f"  检查异常（{i+1}/{max_retries}）: {e}")

        remaining = max_retries - i - 1
        if remaining > 0:
            print(f"⏳ {desc}（{i+1}/{max_retries}，{interval_sec}秒后重试...）")
            time.sleep(interval_sec)

    print(f"⚠️ {desc} 超时（已等待 {max_retries * interval_sec} 秒）", file=sys.stderr)
    return False

