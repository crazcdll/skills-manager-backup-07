# 踩坑记录：基础实体（POI / 供应商 / 房型）

---

## ⚠️ 创建供应商后无法直接拿到 contractNo

### 现象

`create-partner.py`（工具49）返回：

```
partnerId          : 4553737
platformContractId : 18127845
```

但上单时 `goodsBaseInfo.contractNo` 需要的是字符串格式（如 `ZSFW-A9-75178816`），
而不是 `platformContractId` 这个数字。

### 原因

工具49 是异步创建接口，只返回平台内部 ID。`contractNo`（原始合同编号）存储在合同服务，
需要单独查询。

### 解决

用 `factory/infra/query-contract.py` 查询：

```bash
python3 factory/infra/query-contract.py --platform-contract-id 18127845
# 输出：contractNo = ZSFW-A9-75178816
```

接口信息：
- appkey：`com.sankuai.contract.mtcontract`
- service：`com.sankuai.meituan.contract.service.ContractService`
- method：`getContractIdMapping(Long contractId)`
- 返回字段：`contractNumber`（即 contractNo）

### 完整 infra 创建链路

```
create-poi.py      → poiId
create-partner.py  → partnerId + platformContractId
query-contract.py  → contractNo（用 platformContractId 查）
create-room.py     → roomId + roomName
```

---

## ⚠️ 创建房型报「TDC创建房型异常，已存在同名物理房型」

### 现象

```
TDC创建房型异常,已存在同名物理房型，且该物理房型未上传图片，请更换房型名称
```

### 原因

房型名称在 TDC（物理层）全局唯一，同名已被占用。

### 解决

`create-room.py` 已内置时间戳追加逻辑（无论是否传 `--room-name`，最终名称均为「前缀+时间戳」），正常使用不会触发此错误。

若仍遇到（例如同一秒内重复执行），直接重跑即可（时间戳每次不同）：

```bash
python3 factory/infra/create-room.py --partner-id <partnerId> --poi-id <poiId>
```

---

## ⚠️ 创建房型报「TDC创建房型异常」（无详细信息）

### 现象

`create-partner.py` 返回成功后立即执行 `create-room.py`，报 TDC 异常但 message 为 null。

### 原因

工具49（创建供应商）是异步接口，返回 partnerId 后供应商创建流程仍在后台执行，
约需 1 分钟才能真正就绪。

### 解决

等待约 1 分钟后重试 `create-room.py`。

