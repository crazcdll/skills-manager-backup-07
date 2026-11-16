# 踩坑记录：Thrift RPC 调用

---

## ⚠️ 位置参数接口需用 parameter_values，不能用 body dict

### 现象

调用签名为 `method(Long var1, Long var2)` 的接口，用 `body={"var1": ..., "var2": ...}` 传参，
接口返回参数错误或方法找不到。

### 原因

`invoke_thrift` 的 `body` 参数是命名参数模式（对应 Thrift struct），
对于原始类型位置参数（`Long var1, Long var2`）必须使用 `parameter_values` 列表。

### 解决

在 `scripts/runner.py` 的 `invoke()` 中使用 `parameter_values` 和 `parameter_types`：

```python
invoke(
    appkey=...,
    service=...,
    method="getContractIdMapping",
    parameter_values=["18127845"],          # 位置参数，字符串形式
    parameter_types=["java.lang.Long"],     # 对应类型
)
```

CLI 层（`factory/` 脚本）通过 `runner.invoke()` 的同名参数透传，无需直接操作 `invoke_thrift`。

---

## ⚠️ appkey / service 不匹配导致「connection list is empty」

### 现象

```
connection list is empty! ... serviceInterface:com.sankuai.xxx.SomeService
```

### 原因

appkey 下没有注册该 service，节点列表为空。常见于：
- appkey 填了 service 所在模块，但 service 实际注册在另一个 appkey 下
- 用错了相近名字的 appkey（如 `com.sankuai.nibcus.inf.idmapping` vs `com.sankuai.contract.mtcontract`）

### 排查

```bash
# 查该 appkey 下有哪些节点
qatest octo nodes <appkey> --env test

# 查某节点暴露的接口列表
qatest octo interfaces <appkey> <ip> <port> --env test
```

### 已知正确映射

| service | appkey |
|---------|--------|
| `com.sankuai.meituan.contract.service.ContractService` | `com.sankuai.contract.mtcontract` |
| `com.sankuai.nibcus.inf.idmapping.client.service.CustomerIdMappingService` | `com.sankuai.nibcus.inf.idmapping` |
| `com.meituan.hotel.biz.platform.goods.facade.standard.MeGoodsFacade` | `com.sankuai.hotel.biz.platform` |
| `com.meituan.hotel.biz.platform.goods.facade.standard.MeInventoryFacade` | `com.sankuai.hotel.biz.platform` |
| `com.meituan.hotel.contract.mta.service.IMtaContractService` | `com.sankuai.hotel.biz.contract` |

