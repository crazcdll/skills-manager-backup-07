# W9：构造房转套餐（通过货盘规则上单）

## 与普通套餐（W4）的区别

| 项目 | 普通套餐（W4） | 房转套餐（通过货盘规则上单）（W9） |
|------|--------------|--------------|
| 上单方式 | 调用 create-package.py（工具10） | **调用货盘规则接口，套餐由系统自动生成** |
| 需要 contractId | 是 | **否** |
| 需要上传 S3 | 否 | **是**（CSV 文件含 goodsId） |
| 套餐 ID 获取 | 等大象推送 spuId | **等系统自动生成后调用 `queryGoods2SpuRecordByPage` 查询** |
| 审核方式 | audit/package/audit.py | **无需手动审核** |

---

## 前置条件

| 所需 ID | 说明 |
|---------|------|
| `partnerId` | 供应商ID（境内预付，partnerType=2） |
| `poiId` | 门店ID（mtPoiId） |
| `roomId` | 逻辑房型ID（门店下已有房型） |
| `roomName` | 逻辑房型名称（与 roomId 对应） |

缺少基础数据 → 先执行 `references/workflows/w8-infra-bootstrap.md`。

---

## 完整流程（分步执行）

按以下步骤依次调用现有工具完成构造，**无需独立编排脚本**：

---

## 分步说明

### Step 1：创建带非房的全日房

> 按 **[W1：构造全日房 → 前置步骤（可选）：创建非房并关联礼包](w1-create-fullday.md)** 执行。

**Step 1-a + 1-b：创建非房并审核**

> 完整执行 **[W3：构造非房 xGoods + 审核](w3-create-non-room.md)**（Step 1 创建 + Step 2 审核，两步都要做）

- ⚠️ **非房必须先审核通过才能关联到全日房，否则创建全日房时报「礼包不可用」**
- 输出：`xGoodsId`（审核通过状态）

**Step 1-c：创建带非房关联的全日房**
- 调用 `hotel_testdata_cli/factory/fullday/create-fullday.py`，将非房信息通过 `rpServiceModel` 传入（详见 w1 前置步骤）
- 输出：`goodsId`
- 全日房为异步接口，等待大象推送或轮询获取 `goodsId`

### Step 2：生成 CSV 文件

- 格式：单列，列名 `goodsId`，写入 Step 1 的 goodsId
  ```
  goodsId
  <goodsId 值>
  ```
- 调用 `hotel_testdata_cli/factory/resource/upload-to-s3.py` 完成（含生成 + 上传）

### Step 3：上传 CSV 到 S3

- 调用 `hotel_testdata_cli/factory/resource/upload-to-s3.py`
- 服务：`msstest.sankuai.com`（测试环境），Bucket：`biz-platform-goods-copy`
- 输出：`download_url`（https 链接，有效期 1 小时）

### Step 4：创建并发布货盘规则

- 调用 `hotel_testdata_cli/factory/hub-strategy/create-strategy.py`
- appKey：`com.sankuai.hotelcrs.supply.hub`
- 核心入参：`--strategy-name`（自定义名称）、`--file-url`（Step 3 的 download_url）
- 脚本内部自动串联 `createStrategy`（草稿）→ `updateStrategyStatus`（发布上线）
- 输出：`strategyId`；发布后系统**自动生成套餐**，无需额外操作

---

## 关键约束

- 房转套餐**不走** create-package.py（工具10），无需 contractId
- S3 上传的 CSV 只有一列 `goodsId`，每行一个 goodsId
- S3 下载链接有效期 1 小时，货盘规则创建后请立即发布，避免链接过期
- 非房与全日房在 Step 1 合并完成，非房信息通过 `rpServiceModel` 传入，**非房必须先审核通过**（走 W3）再创建全日房
- 套餐 ID 查询：调用 `HubStrategyFacade#queryGoods2SpuRecordByPage`，入参 `{strategyId, page, pageSize}`，出参中 `spuId` 非 0 非 null 且 `status=1` 才是有效的房转套餐

---

## 接口信息

| 步骤 | appKey | service/接口 | 协议 |
|------|--------|-------------|------|
| Step 1（非房） | `com.sankuai.hotel.biz.platform` | `MeResourceFacade#submitXgoods` | Thrift |
| Step 1（全日房） | `com.sankuai.hotel.biz.platform` | `MeGoodsFacade#batchCreateGoods` | Thrift |
| Step 3（S3 上传） | `com.sankuai.hotel.biz.platform` | mssapi-mt SDK | HTTP |
| Step 4（创建并发布规则） | `com.sankuai.hotelcrs.supply.hub` | `HubStrategyFacade#createStrategy` + `updateStrategyStatus` | Thrift |

