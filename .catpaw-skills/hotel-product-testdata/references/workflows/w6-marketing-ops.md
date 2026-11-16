# W6：营销报名 / 缓存刷新 / 改价审核 / 上线下线

## 场景覆盖

| 用户意图 | 操作 |
|---------|------|
| 生意助手报名 / 全域通报名 | 营销报名（工具1037） |
| 刷新商品/SPU/门店/货盘缓存 | 缓存刷新（--op 1） |
| 近线价相关价格预测缓存同步（门店 / 商品维度，指定起日形态暂不可用，已禁用） | nearline-price-cache.py sync / sync-goods |
| 近线价相关价格预测缓存查询（单门店日历 / 单门店连住） | nearline-price-cache.py query / query-multi |
| BD 改价审核（通过/驳回） | --op 2 |
| 商家改价审核（通过/驳回） | --op 3 |
| 商品上线 | batchOnlineSwitch status=2 |
| 商品下线 | batchOnlineSwitch status=3 |
| 查询商品详情 | queryGoodsInfo |

---

## 营销报名（工具1037）

参数约束参考：`factory/marketing/schema.json`

两种报名方式（通过 `--mode` 区分）：

### 方式一：供应商+门店报名（新建 Goods 报名）

```bash
python3 factory/marketing/enroll-marketing.py \
  --mode 1 \
  --partner-id <partnerId> \
  --poi-id <poiId> \
  --config-key <configKey>
```

### 方式二：对已有产品报名

```bash
python3 factory/marketing/enroll-marketing.py \
  --mode 2 \
  --product-id <goodsId> \
  --config-key <configKey>
```

### configKey 枚举

| configKey | 含义 |
|-----------|------|
| `notUpscale` | 生意助手（仅生意助手，不含全域通） |
| `upscaleFixed` | 全域通一口价（**最常用**） |
| `upscaleDiscount` | 全域通折扣 |
| `upscaleFixedDiscountMixed` | 全域通一口价折扣混合 |

> 工具1037 是异步接口，code=2027 表示提交成功，结果由大象推送。

---

## 缓存刷新 / 改价审核（工具1031）

参数约束参考：`factory/ops/schema.json`

> ⚠️ 参数名是 `--op`（不是 `--operation-type`）

### 缓存刷新

```bash
python3 factory/ops/cache-refresh-audit.py \
  --op 1 \
  --product-id <goodsId>    # 商品级别
  # 或 --spu-id <spuId>      # SPU 级别（超团/套餐）
  # 或 --poi-id <poiId>      # 门店级别
  # 或 --rp-id <rpId>        # 货盘级别
```

> 四个 ID 参数（product-id / spu-id / poi-id / rp-id）传其中一项即可，对应刷新的粒度不同。

### BD 改价审核

```bash
python3 factory/ops/cache-refresh-audit.py \
  --op 2 \
  --product-id <goodsId> \
  --audit-status 3          # 3=通过（默认），2=驳回
```

### 商家改价审核

```bash
python3 factory/ops/cache-refresh-audit.py \
  --op 3 \
  --product-id <goodsId> \
  --audit-status 3
```

---

## 近线价缓存同步 / 查询（hotel-goodsquery 后门接口）

> **口径修正（2026-11-02 实测 + 本地源码核对）**：本节保留“近线价相关工具”入口，但 `goodsprice/sync`、`syncGoodsPriceByGoodsIds`、`poiSimplePrice`、`multiPoiSimplePrice` 在本地 `hotel-goodsquery master` 中操作的是价格预测缓存（`PREDICT_GOODS_PRICE_POI_DIMENSION`），不是到手价均值近线价。真正的均值近线价有另一组 `goodsSimplePrice/sync` / `multiPoiSimplePriceV2` 路由，本脚本未接入该组，勿混淆；不同写入来源的数据保留策略也不同，不能一概宣称“累积不覆盖”。
>
> **与工具1031 的区别**：工具1031（`cache-refresh-audit.py --op 1`）刷的是商品/SPU/门店/货盘的**报价基础缓存**；近线价是另一套独立缓存（给大搜的参考价），由 hotel-goodsquery 的 HTTP 后门接口单独触发，两者互不替代。

接口形态：RD 自测 HTTP 后门，挂在 hotel-goodsquery 服务实例的 IP:port 上（默认端口 8080），不走域名网关、不接鉴权。所有命令均复用脚本的服务 IP 查询能力，不写死示例 IP。

### 实测结论（2026-11-02）

目标：测试主干 `10.101.52.163:8080`，POI `1090269458208127`，goodsId `600008267820`。

| 接口 | 实测结果 | 判定边界 |
|------|----------|----------|
| 商品同步（不传 startDate） | 日期 `20261102,20261103,20261104`，响应 `SUCCESS`；立即及延时回读目标 `20261102_20261103` 的 `lastUpdateTime` 仍为 `2026-10-30 16:15:23` | 路由可调用，未验证缓存更新成功；未定位原因，禁止直接重试 |
| 商品同步（追加 startDate） | 日期 `20261103,20261104,20261105` + 起日 `20261103`，HTTP 404 | 当前节点返回404，本地 master 未找到对应路由；按用户要求暂不可用、已禁用，等待研发上线后验证开放 |
| multiPoiSimplePrice | 单 POI 查询 `20261102`～`20261105` 返回5个商品及连住/单晚字段 | multi 指连住/多晚；本地 Controller 使用 `Long.parseLong(poiId)`，不支持逗号分隔多 POI |
| poiSimplePrice | 单 POI 入离日查询能返回数据 | 可用于精准回读目标单晚字段 |
| 自动查 IP | 官方换票因缺 Agent 凭据失败；`mtdev octo nodes --env test` 查询成功后，使用 `--node-ip` 完成实测 | 有实现不等于当前环境前置条件齐全；不得声称官方换票链路实测通过 |

源码证据：`hotel-goodsquery/.../server/controller/CacheController.java:1077-1091`（商品同步唯一映射）、`:3028-3034`（单 POI 连住查询）；本地 master 仅作为源码参考，不等于测试节点部署版本。运行时 Lion 配置及本次未写入根因未验证。

### 服务 IP 查询与公共参数

- 未指定 `--node-ip`：脚本以默认 appkey `com.sankuai.hotelcrs.goodsquery`（可用 `--appkey` 覆盖），执行 `npx --yes mtsso-moa-local-exchange --audience 60921859` 换票，再请求 OCTO 测试环境 `https://octo.mws-test.sankuai.com/api/octo/v2/thriftcheck/serverNodes`（`env=test`），从节点列表中选择 IP。
- 官方换票依赖 Agent 凭据（`AGENT_SSO_CLIENT_ID` / `AGENT_SSO_CLIENT_SECRET` 或官方配置源）及 MOA 登录态，缺失时停止，不猜测/复制其他技能凭据。当前环境实测缺少该前置条件。
- 可独立用已安装并认证的 `mtdev octo --format json nodes com.sankuai.hotelcrs.goodsquery --env test` 查询最新节点，确认目标环境/泳道后传 `--node-ip`；这是显式节点输入路径，不代表脚本换票链路成功，不使用截图里的旧 IP。
- 指定 `--swimlane <泳道>`：严格匹配该泳道节点；找不到则报错停止，**禁止回退主干**。未指定泳道时只选择无泳道节点，找不到也停止。
- 指定 `--node-ip <IP>`：跳过换票及 OCTO 查询，直接使用该 IP。与 `--swimlane` 同时传入时 IP 优先，脚本不校验其泳道归属，调用前需自行确认。
- HTTP 端口默认为 `8080`，可用 `--port` 覆盖；OCTO 查询的是节点 IP，不能拿 Thrift 端口替代 HTTP 后门端口。
- `--dry-run`：仅校验参数和预览 URL，**不换票、不查节点、不调用业务接口**；未传 IP 时 URL 中显示 `{节点IP}` 占位符。

> 以下命令均在 `hotel_testdata_cli/` 下执行。除 `--dry-run` 外，所有 `sync` / `sync-goods` 都会写缓存；即使使用 GET，也不得作为无写入能力探测，不因超时直接重试。

### 同步近线价缓存（模拟用户请求，触发缓存写入）

```bash
python3 factory/ops/nearline-price-cache.py sync \
  --poi-id <poiId>
  # 可选：--swimlane <泳道>（严格匹配，找不到则停止）
  # 可选：--node-ip <ip>（已知节点 IP 时跳过 OCTO 查询）
```

实际调用：`GET http://{节点IP}:8080/cache/goodsprice/sync/{poiId}`

### 商品维度同步：按变更日期集合（实际窗口由服务端控制）

```bash
python3 factory/ops/nearline-price-cache.py sync-goods \
  --goods-id <goodsId> \
  --dates <yyyyMMdd,yyyyMMdd,...>
```

实际调用：`GET http://{节点IP}:8080/cache/syncGoodsPriceByGoodsIds/sync/{goodsId}/{dateString}`。

### 商品维度同步：指定起日形态（暂不可用，已禁用）

仅保留接口契约备忘：`GET /cache/syncGoodsPriceByGoodsIds/sync/{goodsId}/{dateString}/{startDate}`，**不是当前可执行能力**。可能为研发新加、尚未部署的接口；本次仅确认目标测试节点返回404，不断言所有环境均不存在。

- `--start-date` 暂时保留用于给旧调用明确提示，但传入即报错（含 `--dry-run`），在换票/查节点/业务 HTTP 调用前终止，不再组装此路径。
- Agent 不得选择该能力、直接 curl/RPC 绕过禁用、轮询探测或自行开放；不得静默删除起日参数，改用不带起日的同步形态。
- 重新开放条件：研发明确确认目标环境接口已上线 → 核对路由及参数语义 → 按写缓存验证流程实测接口响应与对应缓存回读 → 验证通过后同步解除脚本拦截、更新本工作流及能力地图。
- 此禁用仅针对带 `startDate` 的形态，不影响不带起日同步和查询命令；不带起日同步仍需回读验证，不能把此前 `SUCCESS` 当作更新成功。

**参数边界**：
- `--dates` 对应 `dateString`，是逗号分隔的有效日期列表，**不是 N 的整数值**；保留原序与重复项，不自动扩展、排序或去重。
- `--dates` 在本地源码中转换为 `changeDates` 集合，与服务端更新窗口内的入住日期取交集；传3个日期不等于一定写3天。窗口由服务端和 `mqPredictPriceCheckInFormNow` / `openSerialDays` 等 Lion 运行时配置控制，本次未查实际配置。
- `--start-date` **暂不可用、已禁用**：传入即在网络调用前报错，不能作为可选同步参数使用；研发确认上线并完成回读验证后才重新开放。
- 当前仅支持单个 `--goods-id`；虽然接口名含 `GoodsIds`，但提供的契约示例只有单商品，未确认前不开放批量商品。

### 查询单门店近线价缓存（验证写入是否成功 / 平均值是否正确）

```bash
python3 factory/ops/nearline-price-cache.py query \
  --poi-id <poiId> \
  --check-in <yyyyMMdd> \
  --check-out <yyyyMMdd>
```

实际调用：`GET http://{节点IP}:8080/cache/poiSimplePrice/{poiId}/{checkIn}/{checkOut}`（日期格式 yyyyMMdd）

### 查询单门店连住/多晚价格预测缓存（multi 非多门店）

```bash
python3 factory/ops/nearline-price-cache.py query-multi \
  --poi-ids <poiId> \
  --start-day <yyyyMMdd> \
  --end-day <yyyyMMdd>
```

实际调用：`GET http://{节点IP}:8080/cache/multiPoiSimplePrice/{poiId}/{startDay}/{endDay}`。

`--poi-ids` 保留上一版 CLI 参数名，但仅接受一个 POI，多个 ID 会在请求前报错。`--start-day` / `--end-day` 对应入住/离店区间；服务端可返回连住字段及区间内的单晚字段，例如 `20261102_20261105`、`20261102_20261103` 等。若只验证单晚同步，使用相应单晚入离日精准回读。结束日期不能早于开始日期；单门店 `query` 的离店日期必须晚于入住日期。

> 典型使用场景：① 验证近线价缓存是否正确写入；② 验证平均值计算是否正确；③ 排查大搜侧展示价格与近线价不符的问题。HTTP 调用完成不等于业务成功，应检查响应；同步后用 `query` / `query-multi` 回读验证。

---

## 商品上线 / 下线（batchOnlineSwitch）

> ⚠️ `--goods-ids` 可传多个（空格分隔）；`--partner-id` 和 `--poi-id` 必填

```bash
# 上线（恢复上线）
python3 factory/ops/online-switch.py \
  --partner-id <partnerId> \
  --poi-id <poiId> \
  --goods-ids <goodsId> \
  --status 2                # 2=上线

# 下线
python3 factory/ops/online-switch.py \
  --partner-id <partnerId> \
  --poi-id <poiId> \
  --goods-ids <goodsId> \
  --status 3                # 3=下线（注意：不是1！）

# 批量上线多个商品
python3 factory/ops/online-switch.py \
  --partner-id <partnerId> \
  --poi-id <poiId> \
  --goods-ids <goodsId1> <goodsId2> \
  --status 2
```

> 上线失败且报"最近90天内至少30天同时有价格和库存"时，先执行 `references/workflows/w7-inventory-ops.md` 开房设库存，再重新上线。

---

## 查询商品详情（queryGoodsInfo）

```bash
python3 factory/ops/query-goods.py \
  --partner-id <partnerId> \
  --poi-id <poiId> \
  --goods-ids <goodsId>
  # 支持多个 goodsId（空格分隔）
  # 可选：--field rpCancelModel   只打印特定字段
```

---

## 关键约束

- `--op` 是 cache-refresh-audit.py 的参数名（不是 `--operation-type`）
- 近线价操作走 `nearline-price-cache.py`（hotel-goodsquery 后门 HTTP 接口，IP 直连），与工具1031 的报价基础缓存刷新是两套缓存，互不替代
- `sync` / `sync-goods` 是写缓存操作，即使 GET 也不应直接重试；`--dry-run` 全程无网络调用
- 指定泳道找不到节点时停止，不回退主干；服务 IP 自动查询或由 `--node-ip` 显式指定
- 商品**下线** status=`3`，**上线** status=`2`（不是 1！1 在内部枚举中有其他含义）
- online-switch.py 必须传 `--partner-id`、`--poi-id`、`--goods-ids`，三者缺一不可
- 营销报名必须先指定 `--mode 1`（供应商+门店）或 `--mode 2`（productId），两者互斥
- 改价审核必须传 `--audit-status`（2=驳回 / 3=通过），--op=3（商家改价）默认通过

