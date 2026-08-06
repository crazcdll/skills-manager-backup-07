# 共用枚举速查

> 跨场景（全日房/钟点房/套餐/超团）均适用的枚举值。
> 场景专属字段说明见各场景 factory 目录下的 `schema.json`（如 `factory/fullday/schema.json`）。

---

## goodsType（商品类型）

| 值 | 含义 |
|----|------|
| `1` | 全日房 |
| `2` | 钟点房 |

---

## paymentType（支付类型）

| 值 | 含义 | 担保规则要求 |
|----|------|------------|
| `0` | 预付（默认） | 不传 rpGuaranteeModel |
| `1` | 现付担保 | isGuarantee=1，guaranteeType 必填 |
| `2` | 现付非担保 | isGuarantee=0，arrivalHour 必填（默认 14:00:00） |

---

## sellChannel（售卖渠道）

| 值 | 含义 |
|----|------|
| `null`/不传 | 全平台（美团+点评，默认） |
| `9` | 仅美团 |
| `10` | 仅点评 |

---

## cancelItemType（取消类型，rpCancelModel 内部字段）

| 值 | 含义 |
|----|------|
| `0` | 不可取消 |
| `1` | 可取消（免费或收费） |

---

## guaranteeType（担保类型，rpGuaranteeModel 内部字段）

| 值 | 含义 | 适用场景 |
|----|------|---------|
| `1` | 首晚担保 | paymentType=1 |
| `2` | 整单担保（推荐默认） | paymentType=1 或 2 |

---

## isAutoRelay（自动延期，rpBaseModel 内部字段）

| 值 | 含义 |
|----|------|
| `0` | 开启自动延期（默认） |
| `1` | 关闭自动延期 |

---

## customNameType（产品备注类型，rpBaseModel 内部字段）

| 值 | 含义 |
|----|------|
| `0` | 未自定义备注（默认） |
| `1` | 已自定义备注（传了 rpCustomName 时用） |

---

## priceRecordWay（价格录入方式）

| 值 | 含义 |
|----|------|
| `1` | 卖价录入（默认，用户直接填售价） |
| `2` | 底价录入（BP 链路，系统计算卖价） |

---

## 专客专享枚举（rpDisplayModel 内部字段）

| 字段 | 值 | 含义 |
|------|----|------|
| `hotelMember` | `0` | 全部用户 |
| `hotelMember` | `1` | 一档会员 |
| `hotelMember` | `2` | 二档会员 |
| `totalGmv` | `0` | 全部用户 |
| `totalGmv` | `1` | 一档GMV |
| `totalGmv` | `2` | 二档GMV |
| `city` | `0` | 全城市 |
| `city` | `1` | 下单城市在POI城市 |
| `city` | `2` | 下单城市不在POI城市 |
| `stuSpecial` | `0` | 全部用户 |
| `stuSpecial` | `1` | 仅学生专享 |
| `distanceRange` | `0` | 全部用户 |
| `distanceRange` | `1` | POI 3公里内（附近专享） |
| `riskControl` | `0` | 全部用户 |
| `riskControl` | `1` | 黑名单用户不可见 |
| `employeeExclusive` | `0` | 全部用户 |
| `employeeExclusive` | `1` | 仅美团在职员工 |

> **`rpDisplayModel` 始终传递**（interface 层无论全为 0 还是非 0 都会传），全为 0 表示「全部用户可见，不做限制」。
> 如需关闭专客专享，将所有字段保持默认 0 即可，无需手动删除此字段。

---

## getProcessRate 返回状态（异步轮询）

| data.status | 含义 |
|-------------|------|
| `0` | 处理中，继续轮询 |
| `1` | 创建成功，取 data.goodsId |
| `2` | 创建失败，取 data.message 查看原因 |

