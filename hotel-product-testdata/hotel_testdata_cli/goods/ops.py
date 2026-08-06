#!/usr/bin/env python3
"""
商品创建公共操作

call_raw          - 调 batchCreateGoods RPC
wait_for_goods_id - 轮询等待异步任务，返回 goodsId
post_create_ops   - 上线 + 库存补偿 + 缓存刷新

原 interface/goods/interface.py 合并于此。
"""

import datetime
import importlib.util as _ilu
import json
import os
import time

from hotel_testdata_cli.scripts.runner import invoke, InvokeError, StepError  # noqa

APPKEY  = "com.sankuai.hotel.biz.platform"
SERVICE = "com.meituan.hotel.biz.platform.goods.facade.standard.MeGoodsFacade"
METHOD  = "batchCreateGoods"

_INV_ERROR_KEYWORD = "最近90天内至少30天同时有价格和库存"

# goods/ops.py 在 hotel_testdata_cli/goods/ 下，上两级是 hotel-testdata-cli/ 根
_skill_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))


def _today() -> str:
    return datetime.date.today().strftime("%Y-%m-%d")


def _inv_end_date() -> str:
    today = datetime.date.today()
    try:
        end = today.replace(year=today.year + 2) - datetime.timedelta(days=1)
    except ValueError:
        end = today.replace(year=today.year + 2, month=3, day=1) - datetime.timedelta(days=1)
    return end.strftime("%Y-%m-%d")


# ════════════════════════════════════════════════════════════════════════════
# 接口层兜底校验
# ════════════════════════════════════════════════════════════════════════════

def _validate_raw(params: dict) -> None:
    def _get(obj, *path):
        cur = obj
        for k in path:
            if isinstance(cur, list):
                try:
                    cur = cur[int(k)]
                except (IndexError, ValueError, TypeError):
                    return None
            elif isinstance(cur, dict):
                cur = cur.get(k)
            else:
                return None
        return cur

    errors = []
    gd = _get(params, "goodsDetailList", "0") or {}
    base = gd.get("goodsBaseInfo") or {}
    rp = gd.get("rpInfo") or {}
    price_info = gd.get("priceInfo") or {}

    goods_type   = base.get("goodsType", 1)
    payment_type = base.get("paymentType", 0)
    goods_name   = base.get("goodsName", "")

    if goods_name and "测试" in goods_name:
        errors.append("R1: goodsName 不能包含'测试'字样（后端拦截）")

    if goods_type == 2:
        type_limit = base.get("typeLimitValue")
        if type_limit is None:
            errors.append("R2: 钟点房必须传 typeLimitValue（可住时长，小时）")
        else:
            try:
                tl = int(type_limit)
                if not (1 <= tl <= 23):
                    errors.append(f"R2: typeLimitValue={tl} 超出范围（必须 1~23）")
            except (ValueError, TypeError):
                errors.append(f"R2: typeLimitValue={type_limit} 不是整数")

    if goods_type == 2 and rp.get("rpBreakFastModel") is not None:
        errors.append("R3: 钟点房不支持 rpBreakFastModel，必须为 null")

    if payment_type == 2:
        guarantee_model = (rp.get("rpGuaranteeModel") or {}).get("normalRule") or {}
        if not guarantee_model.get("arrivalHour"):
            errors.append("R4: paymentType=2（现付非担保）时 arrivalHour 必填")

    sale_price_str = _get(
        price_info, "unifiedDatePriceInfos", "weekPriceInfos", "0", "priceInfo", "salePrice"
    )
    if sale_price_str is not None:
        try:
            sp = int(sale_price_str)
            if sp <= 0:
                errors.append(f"R5: salePrice={sp} 非法，必须 > 0（单位：分）")
        except (ValueError, TypeError):
            pass

    if errors:
        msg = "\n".join(f"  {e}" for e in errors)
        raise ValueError(f"接口层参数校验失败（共 {len(errors)} 项）：\n{msg}")


# ════════════════════════════════════════════════════════════════════════════
# call_raw
# ════════════════════════════════════════════════════════════════════════════

def call_raw(
    params: dict,
    swimlane: str = "",
    dry_run: bool = False,
) -> dict:
    """将完整 batchCreateGoods 参数 dict 发给 RPC。"""
    _validate_raw(params)

    goods_type = 1
    try:
        goods_type = int(
            (params.get("goodsDetailList") or [{}])[0]
            .get("goodsBaseInfo", {})
            .get("goodsType", 1)
        )
    except (IndexError, AttributeError, TypeError, ValueError):
        pass

    return invoke(
        appkey=APPKEY,
        service=SERVICE,
        method=METHOD,
        params=params,
        swimlane=swimlane,
        timeout_ms=120000,
        dry_run=dry_run,
        raise_on_biz_error=True,
        progress_hint=f"创建{'全日房' if goods_type == 1 else '钟点房'}（研发接口）中，约30秒...",
    )


# ════════════════════════════════════════════════════════════════════════════
# wait_for_goods_id
# ════════════════════════════════════════════════════════════════════════════

def _query_process_rate(partner_id: str, poi_id: str, uuid: str, swimlane: str = "") -> dict:
    return invoke(
        appkey=APPKEY,
        service=SERVICE,
        method="getProcessRate",
        parameter_values=[str(int(partner_id)), str(int(poi_id)), f'"{uuid}"'],
        parameter_types=["java.lang.Long", "java.lang.Long", "java.lang.String"],
        swimlane=swimlane,
        timeout_ms=30000,
        raise_on_biz_error=False,
        progress_hint="查询创建进度...",
    )


def wait_for_goods_id(
    partner_id: str,
    poi_id: str,
    uuid: str,
    swimlane: str = "",
    timeout_sec: int = 120,
) -> str:
    """轮询等待 batchCreateGoods 异步任务完成，返回 goodsId。"""
    interval = 5
    max_attempts = max(1, timeout_sec // interval)

    for attempt in range(1, max_attempts + 1):
        try:
            rate_result = _query_process_rate(partner_id, poi_id, uuid, swimlane)
            data = rate_result.get("data") or {}
            if data.get("over", False):
                error_type = data.get("errorType", 0)
                result_str = data.get("result") or ""
                goods_id = ""
                if result_str:
                    try:
                        result_list = json.loads(result_str)
                        if isinstance(result_list, list) and result_list:
                            goods_id = str(result_list[0].get("goodsId") or result_list[0].get("productId") or "")
                        elif isinstance(result_list, dict):
                            goods_id = str(result_list.get("goodsId") or result_list.get("productId") or "")
                    except Exception:
                        goods_id = ""
                # errorType!=0 但 result 里已有 goodsId（如 errorType=2 保存草稿失败）
                # 商品主体已创建成功，打印警告后继续走上线流程
                if error_type != 0:
                    err_msg = data.get("message") or "创建失败"
                    if goods_id:
                        print(f"  ⚠️ 商品创建部分失败（errorType={error_type}）: {err_msg}")
                        print(f"  ℹ️ 已获取到 goodsId={goods_id}，继续执行上线流程...")
                    else:
                        raise StepError("wait_for_goods_id", f"商品创建失败: {err_msg}")
                return goods_id
            else:
                print(f"   第{attempt}/{max_attempts}次轮询：处理中...（等待{interval}秒）")
        except StepError:
            raise
        except Exception as e:
            print(f"   轮询异常（{attempt}/{max_attempts}次）: {e}")

        if attempt < max_attempts:
            time.sleep(interval)

    print(f"⚠️ 已轮询 {max_attempts} 次（{timeout_sec}秒）仍未完成，商品可能仍在处理中。")
    return ""


# ════════════════════════════════════════════════════════════════════════════
# post_create_ops：上线 + 库存补偿 + 缓存刷新
# ════════════════════════════════════════════════════════════════════════════

def _resolve_interface_path(subpkg: str, filename: str) -> str:
    """
    查找 interface/<subpkg>/<filename> 的绝对路径。

    与 registry.py 的 _resolve_script_path 策略一致：
      1. importlib.resources（pip install 正式安装后，从包数据里找）
      2. 文件系统相对路径（pip install -e 本地开发模式）
    """
    # ── 方式1：importlib.resources（正式安装场景） ───────────────────────────
    try:
        from importlib.resources import files, as_file
        pkg_name = f"hotel_testdata_cli.interface.{subpkg}"
        pkg_path = files(pkg_name).joinpath(filename)
        with as_file(pkg_path) as p:
            if p.exists():
                return str(p)
    except (ModuleNotFoundError, TypeError, FileNotFoundError, AttributeError):
        pass

    # ── 方式2：文件系统（本地 -e 开发模式） ─────────────────────────────────
    fs_path = os.path.join(_skill_root, "interface", subpkg, filename)
    if os.path.isfile(fs_path):
        return fs_path

    raise FileNotFoundError(
        f"找不到 interface/{subpkg}/{filename}\n"
        f"  已尝试包路径：hotel_testdata_cli.interface.{subpkg}\n"
        f"  已尝试文件系统路径：{fs_path}"
    )


def _load_ops_interface():
    path = _resolve_interface_path("ops", "interface.py")
    spec = _ilu.spec_from_file_location("_hotel_interface_ops", path)
    mod = _ilu.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _load_update_inventory():
    """加载 factory/inventory/update-inventory.py（与 registry.py 策略一致）。"""
    # 先给文件系统路径作为默认值（本地 -e 开发模式），使用模块级 _skill_root
    inv_path = os.path.join(_skill_root, "factory", "inventory", "update-inventory.py")

    # 尝试 importlib.resources（正式安装后优先走这里）
    try:
        from importlib.resources import files, as_file
        pkg_path = files("hotel_testdata_cli.factory.inventory").joinpath("update-inventory.py")
        with as_file(pkg_path) as p:
            if p.exists():
                inv_path = str(p)
    except Exception:
        pass

    if not os.path.isfile(inv_path):
        raise FileNotFoundError(f"找不到 update-inventory.py：{inv_path}")

    spec = _ilu.spec_from_file_location("_hotel_factory_inventory", inv_path)
    mod = _ilu.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def post_create_ops(
    partner_id: str,
    poi_id: str,
    goods_id: str,
    params: dict,
    room_id: int,
    swimlane: str = "",
    goods_type: int = 1,
) -> None:
    """
    商品创建后置操作：
      Step 6：恢复上线（batchOnlineSwitch status=2）
      Step 7：缓存刷新
    上线失败含"90天库存"时自动补库存后重试。
    """
    if not goods_id:
        print("\n⚠️ 未获取到 goodsId，跳过上线和缓存刷新。")
        return

    ops = _load_ops_interface()

    def _try_online(gid: str):
        print("\n── Step 6: 恢复上线（batchOnlineSwitch status=2）──────────────")
        try:
            switch_resp = ops.call_online_switch(
                partner_id=int(partner_id),
                poi_id=str(poi_id),
                goods_ids=[int(gid)],
                status=2,
                swimlane=swimlane,
            )
            sw_data = switch_resp.get("data") or {}
            if sw_data.get("successCount", 0) > 0 and sw_data.get("failCount", 0) == 0:
                print("  ✅ 上线成功")
                return True, ""
            else:
                details = sw_data.get("details") or []
                reason = details[0].get("reason", "未知原因") if details else "未知原因"
                return False, reason
        except Exception as e:
            return False, str(e)

    def _do_cache_refresh(gid: str):
        print("\n── Step 7: 缓存刷新（operationType=1）───────────────────────")
        try:
            ops.call(operation_type=1, product_id=int(gid))
            print("  ✅ 缓存刷新成功")
        except Exception as e:
            print(f"  ⚠️ 缓存刷新失败（可手动触发）: {e}")

    success, reason = _try_online(goods_id)
    if success:
        _do_cache_refresh(goods_id)
        return

    if _INV_ERROR_KEYWORD not in reason:
        print(f"  ⚠️ 上线未成功: {reason}（可在 MTA 手动操作）")
        _do_cache_refresh(goods_id)
        return

    print(f"  ⚠️ 上线失败（{reason}）")
    print("  🔄 检测到库存不足，调用 batchUpdateInventory 开房并设置库存...")

    try:
        dates = params["goodsDetailList"][0]["priceInfo"]["unifiedDatePriceInfos"]["dates"]
        start_date = dates[0]["startDate"]
        end_date   = dates[0]["endDate"]
        max_end = _inv_end_date()
        if end_date > max_end:
            end_date = max_end
    except (KeyError, IndexError, TypeError):
        start_date = _today()
        end_date   = _inv_end_date()

    print(f"  [库存修改] 房型={room_id}，日期范围 {start_date} ~ {end_date}")

    room_id_int = int(room_id)
    room_kwarg  = "day_room_ids" if goods_type == 1 else "hour_room_ids"
    # 新建商品首次设库存，必须用 1121（绝对量覆盖）；1520 是增量叠加，新房型会报错
    count_type  = 1121

    _INV_DEP_ERR = "依赖系统返回失败"
    _INV_MAX_RETRY = 3
    _INV_RETRY_INTERVAL = 30  # 秒，每次递增

    inv_ok = False
    inv_last_err = None
    for inv_attempt in range(_INV_MAX_RETRY):
        try:
            upd_mod = _load_update_inventory()
            upd_mod.open_and_set_inventory(
                partner_id=partner_id,
                poi_id=poi_id,
                **{room_kwarg: [room_id_int]},
                start_date=start_date,
                end_date=end_date,
                inv_switch=1,
                count_type=count_type,
                limit_change_value=299,
                count=1,
                swimlane=swimlane,
            )
            inv_ok = True
            print("  ✅ 库存修改成功，重新尝试上线...")
            break
        except Exception as e:
            inv_last_err = e
            err_str = str(e)
            if _INV_DEP_ERR in err_str and inv_attempt < _INV_MAX_RETRY - 1:
                wait = _INV_RETRY_INTERVAL * (inv_attempt + 1)
                print(f"  ⏳ 库存服务依赖未就绪，{wait}秒后重试"
                      f"（{inv_attempt + 1}/{_INV_MAX_RETRY}）...")
                time.sleep(wait)
            else:
                break

    if not inv_ok:
        room_arg_name = "--day-room-ids" if goods_type == 1 else "--hour-room-ids"
        print(f"  ⚠️ 库存修改失败: {inv_last_err}")
        print(f"  💡 可手动执行：python3 factory/inventory/update-inventory.py"
              f" --partner-id {partner_id} --poi-id {poi_id}"
              f" {room_arg_name} {room_id_int}"
              f" --start-date {start_date} --end-date {end_date}"
              f" --inv-switch 1 --count-type 1121 --limit-change-value 299 --count 1")
        _do_cache_refresh(goods_id)
        return

    success2, reason2 = _try_online(goods_id)
    if not success2:
        print(f"  ⚠️ 补库存后仍上线失败: {reason2}（可在 MTA 手动操作）")
    _do_cache_refresh(goods_id)

