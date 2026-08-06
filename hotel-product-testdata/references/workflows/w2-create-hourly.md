# W2：构造钟点房（钟点房 batchCreateGoods）

## 场景覆盖

| 用户描述 | 关键参数差异 |
|---------|------------|
| 普通钟点房（4小时，免费取消） | 默认模板，无需额外 --set |
| 自定义时长（2/3/6/8小时） | typeLimitValue=N |
| 不可取消钟点房 | cancelItemType=0 |
| 自定义接待时间（如全天/下午场） | receiveTimeStart/receiveTimeEnd |
| 周末不同取消规则 | rpCancelModel.weekendRule |
| 带非房/带礼包 | 先按 W3 创建并审核非房，再在 Step 1 命令中追加 `--set goodsDetailList.0.rpInfo.rpServiceModel=...`，详见下方「前置步骤（可选）」 |

---

## 前置条件

进入本 workflow 前，必须已就绪：`partnerId`、`poiId`、`roomId`、`roomName`、`contractNo`（字符串如 `ZSFW-A9-75178816`）。

> ⚠️ **`contractNo` 对钟点房同样必填**：接口会校验合同不得为空，缺失会报「合同不能为空」。需先用 `query-contract.py --platform-contract-id <id>` 查询得到字符串格式，再通过 `--contract-no` 参数传入。

缺少任何一项 → 先执行 `references/workflows/w8-infra-bootstrap.md`。

---

## 前置步骤（可选）：创建非房并关联礼包

> 仅当产品需要绑定礼包（非房）时执行。普通钟点房跳过，直接进入 Step 1。

> ⚠️ 字段映射规则与全日房完全一致，详见 **[W1：构造全日房](w1-create-fullday.md)** 中的「前置步骤（可选）：创建非房并关联礼包」。

### ① 按 [W3：构造非房 xGoods + 审核](w3-create-non-room.md) 完成非房创建

```bash
python3 factory/non-room/create-non-room.py \
  --partner-id <partnerId> \
  --poi-id <poiId> \
  [--product-name "<礼包名称>"]
# 输出：xGoodsId（同步返回，无需等待）
```

### ② 查询非房详情

用创建返回的 `xGoodsId` 查询非房完整信息（`MeResourceFacade#queryXgoodsListByPage`），入参：`partnerId`、`poiId`、`xgoodsId`。

### ③ 在 Step 1 创建钟点房命令中追加 `--set` 参数（组装 rpServiceModel）

非房信息通过 **`rpServiceModel`** 传递，将查询结果映射到 `serviceModels[0]` 中，映射规则见 W1 前置步骤的字段映射表。

```bash
--set 'goodsDetailList.0.rpInfo.rpServiceModel={"normalRule":{"serviceModels":[{"serviceTmplId":<xGoodsId>,"serviceName":"<name>","serviceType":12,"serviceItemType":3,"remark":"<content>","availableDate":"","availableDateType":0,"serviceCategory":1,"serviceTemplate":<priType>,"servicePriceStd":"0","servicePrice":0,"serviceContent":{...}}]},"updateType":0}'
```

---

## Step 1：组装命令

> 参数约束：`factory/hourly/schema.json` | 默认值：`factory/hourly/templates/hourly-default.json`

**基础命令**：

```bash
python3 factory/hourly/create-hourly.py \
  --partner-id <partnerId> \
  --poi-id <poiId> \
  --room-id <roomId> \
  --room-name "<roomName>" \
  --contract-no <contractNo> \
  [--set KEY=VALUE ...]
```

> ⚠️ `create-hourly.py` **没有 `--mis` 参数**，脚本通过环境变量自动读取操作人。
> `contractNo` 需通过 `--contract-no <contractNo>` 参数传入（推荐）或 `--set goodsDetailList.0.goodsBaseInfo.contractNo=<contractNo>`（兼容）。

---

## Step 2：按用户描述追加 --set 参数

### 可住时长

```bash
--set goodsDetailList.0.goodsBaseInfo.typeLimitValue=4   # 默认4小时，范围 1~23
```

常用预设：2h / 3h / 4h（默认）/ 6h / 8h / 12h

### 取消政策

| 场景 | --set 参数 |
|-----|-----------|
| 免费取消（默认，当天23:59前） | 无需设置（已是默认） |
| 不可取消 | `goodsDetailList.0.rpInfo.rpCancelModel.normalRule.cancelItemType=0` |
| 周末不同取消规则 | `'...rpCancelModel.weekendRule={"cancelItemType":1,"moveUpCancelDays":0,"moveUpCancelHour":"18:00:00"}'` |

> ⚠️ 钟点房**不支持收费取消**（payCancelPeriodModels），传了报错。
> ⚠️ 钟点房 `paymentType` 固定为 0（预付），不支持现付。

### 接待时间

| 场景 | --set 参数 |
|-----|-----------|
| 标准（08:00-22:00，默认） | 无需设置 |
| 全天接待 | `...receiveTimeStart=00:00` + `...receiveTimeEnd=23:59` |
| 下午场（14:00-20:00） | `...receiveTimeStart=14:00` + `...receiveTimeEnd=20:00` |

完整路径：`goodsDetailList.0.rpInfo.rpHourlyRoomUseModel.normalRule.receiveTimeStart`

> ⚠️ `typeLimitValue` 必须 ≤（receiveTimeEnd - receiveTimeStart）的小时差，否则报「可住时间小于入住时长」。

### 售价

```bash
--set goodsDetailList.0.priceInfo.unifiedDatePriceInfos.weekPriceInfos.0.priceInfo.salePrice=8000
# 单位：分，8000=80元（钟点房默认，低于全日房的20000）
```

> ⚠️ **钟点房仅支持境内**，不存在境外钟点房场景。无需设置 `priceSameTag` / `priceFactorInfos`，也不支持多人多价。

---

## Step 3：dry-run 确认（必做）

```bash
python3 factory/hourly/create-hourly.py [全部参数] --dry-run
```

确认输出中 `[约束校验] ✅ 通过` 且最终参数结构符合预期，再去掉 `--dry-run` 正式执行。

---

## Step 4：执行创建

```bash
python3 factory/hourly/create-hourly.py [全部参数]
```

成功后脚本**自动**依次执行：

1. **恢复上线**（batchOnlineSwitch status=2）
2. **开房设库存**（若上线失败且原因含"最近90天内至少30天同时有价格和库存"）：自动调用 batchUpdateInventory（invSwitch=1，countType=1520，limitChangeValue=299），再重新上线
   > ⚠️ 自动步骤用 countType=1520（设置余量）。**全新商品首次添加库存**时可能因"不能选择不变"再次失败 → 走下方手动步骤，改用 `--count-type 1121`
3. **缓存刷新**（operationType=1）

自动步骤失败时脚本打印完整手动命令，直接复制执行即可。

---

## Step 5：手动补操作（自动步骤失败时）

**手动开房+设库存**（全新商品首次添加库存用 `--count-type 1121`；已有库存记录用 `1520`；⚠️ 钟点房用 `--hour-room-ids`，全日房用 `--day-room-ids`）：
```bash
python3 factory/inventory/update-inventory.py --partner-id <partnerId> --poi-id <poiId> --hour-room-ids <roomId> --start-date <今天日期> --end-date <今天+2年-1天> --inv-switch 1 --count-type 1121 --limit-change-value 299 --count 1
```

---

## 与全日房的关键差异

| 项目 | 全日房 | 钟点房 |
|-----|--------|--------|
| goodsType | 1 | **2**（固定） |
| typeLimitValue | 不传 | **必填**（1~23小时） |
| rpHourlyRoomUseModel | 必须 null | **必填**（接待时间） |
| rpBreakFastModel | 必传（num≥0） | **固定 null**（不支持早餐） |
| rpSerialModel | 传连住规则 | **固定 null**（不支持连住） |
| paymentType | 0/1/2 | **只支持 0**（预付） |
| 收费取消 | 支持 | **不支持** |
| 默认取消 | 当天18:00前免费取消 | **免费取消（当天23:59前）** |
| 默认售价 | 20000分（200元） | **8000分（80元）** |
| contractNo | **必填**（`--set` 传入） | **必填**（`--contract-no` 参数传入） |
| 库存命令参数 | `--day-room-ids` | `--hour-room-ids` |

---

