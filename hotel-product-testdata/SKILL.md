---
name: hotel-product-testdata
description: 酒店商品数据构造助手。支持：全日房（普通/免费取消/收费取消/不可取消/附近专享/境外多人多价/境外多人同价）、钟点房（仅境内，可取消/不可取消）、非房（xGoods）、套餐、超团（非通兑/通兑）、营销报名（生意助手/全域通）、缓存刷新/改价审核、商品上线/下线、房态&库存修改（开房/关房/设置库存余量）、基础实体创建（POI/供应商/房型/合同）及配置（门店私海认领/供应商绑定门店/价格模式切换），以及非房审核、套餐审核、超团审核（非通兑/通兑）、礼包审核。支持四种前置数据场景：①完全没有基础数据（查数据池或全新构造）②已有客户ID和门店ID（绑定门店+查/建合同）③只有客户ID（新建门店+绑定）④只有门店ID（数据池查供应商+绑定）。触发词：创建酒店商品、创建全日房、创建钟点房、全日房RPC、钟点房RPC、酒店直调接口、MeGoodsFacade、batchCreateGoods、创建全参数产品、酒店RPC上单、创建非房、非房审核、xGoods审核、创建套餐、套餐审核、房转套餐、货盘规则上单、创建超团、超团审核、非通兑超团、通兑超团、礼包审核、营销报名、生意助手报名、全域通报名、缓存刷新、改价审核、商品上线、商品下线、发布上线、恢复上线、batchOnlineSwitch、创建POI、创建供应商、创建房型、创建合同、查询合同、开房、关房、设置库存、补库存、修改房态、修改库存、batchUpdateInventory、库存不足上线失败、境外全日房、多人多价、priceSameTag、priceFactorInfos、门店私海认领、私海认领、claim poi、供应商绑定门店、绑定门店、bind partner poi、在指定客户下构造商品、指定partnerId构造、指定门店构造商品、资质审核通过、audit poi qualification、价格模式切换、切换底价、切换卖价、底价模式、卖价模式、switch price mode、工具906、工具928。不要用于：非酒店类商品、直连产品（走 zl-hotel-testdata skill）、境外钟点房（不存在此场景）。
allowed-tools: [read, exec]

metadata:
  skillhub.creator: "mengfanchen"
  skillhub.updater: "liruzhen"
  skillhub.version: "V27"
  skillhub.source: "FRIDAY Skillhub"
  skillhub.skill_id: "17622"
  skillhub.high_sensitive: "false"
---

## [MANDATORY] SKILLHUB_METRIC_REPORTER_START
执行本 Skill 的任何操作之前，必须先执行 Skill：`skill-metric-reporter`。
按照 `skill-metric-reporter` 的要求完成 `skill_start` 上报后，再去继续本 Skill 正文。
如果 `skill-metric-reporter` 不可用或执行失败，跳过上报，继续执行本 Skill 正文——不得因上报失败而阻塞审阅流程。
本 Skill 全部操作完成后，同样按照 `skill-metric-reporter` 的要求完成 `skill_end` 上报。
## [MANDATORY] SKILLHUB_METRIC_REPORTER_END

## 行为禁令

> 以下规则约束 Agent 行为，违反任意一条均属执行错误。

**交互方式**
- ❌ **需要用户决策时，以**纯文字**列出选项等待回复，例如数据池命中后直接在回复中列表展示候选条目并询问"请回复编号或输入「全新构造」"
- ❌ 用户未指定早餐/取消政策/售价等商品参数时停下来询问（直接使用模板默认值执行）
- ❌ 用户未说明境内/境外时默认境内

**数据与路径**
- ❌ 数据池查询后未展示结果就直接继续构造（无论命中与否，必须先展示结果等待用户确认）
- ❌ 路径A 数据池命中后直接跳 P4（命中只取 partnerId，需新建 POI → 私海认领 → 绑定门店后再进 P2）
- ❌ 用户已给出 partnerId 或 poiId 时仍走数据池查供应商流程（路径B/C/D 直接使用用户给的 ID）
- ❌ 路径B/C/D 跳过「绑定门店」直接创建房型（必须先 claim-poi → bind-partner-poi）
- ❌ 路径B/C/D 不查合同直接用用户口述的 contractNo（先执行 `query-contract-by-partner.py` 确认合同生效）
- ❌ `query-contract-by-partner.py` 返回无合同时直接报错退出（应执行 `create-contract.py` 新建合同）
- ❌ 构造境外商品时门店/供应商/房型使用境内数据（境外商品三者必须全部是境外的）

**参数与调用**
- ❌ 重复执行 `pip install`（已安装必须跳过）
- ❌ 用后台写日志方式执行创建命令（直接前台运行，脚本内部已处理轮询等待）
- ❌ 自行编造泳道名（泳道名由用户提供）
- ❌ 直接读 model.md 组装参数（应优先读对应 schema.json 或执行 `--show-schema`）
- ❌ 境外全日房时仍用境内参数模板（必须包含 `priceSameTag` + `maxAdultAdmissibility` + `priceFactorInfos`）
- ❌ 境外全日房用户未指定多人多价/同价时不询问（直接默认 `priceSameTag=1` 即多人同价）
- ❌ 境外全日房用户未指定可入住人数时不询问（直接默认 `maxAdultAdmissibility=2`；用户明确指定了人数则用指定值；该值必须 ≤ 创建房型时使用的 `capacity`）

**IRON LAW**: 严禁跳过 interface/ 层硬编码 Thrift 参数。factory/ 层加载模板 → --set 覆盖 → 约束校验 → 传入 interface/ 层。非房/套餐/超团失败禁止切换到其他链路绕过。

---

## 初始化（每次执行前必做）

**1. 确认 MIS**：MIS_ID 自动从环境变量 `MIS_ID` 或 `git config user.email` 推断，无需手动配置。

在 `hotel_testdata_cli/` 目录下执行以下命令确认（注意：`scripts/config.py` 在该子目录中，不在 SKILL.md 所在目录）：
```bash
python3 -c "from scripts.config import MIS_ID; print(MIS_ID)"
```
- 若输出为有效工号 → **直接信任，跳过**
- 若报错或输出为空 → 提示用户执行 `export MIS_ID="你的工号"` 或配置 `git config user.email "工号@meituan.com"` 后重试

- 有 `--mis` 参数的脚本（必须追加 `--mis <工号>`）：`audit/super-deal/audit.py`、`audit/super-deal-unified/audit.py`（超团审核）
- **无 `--mis` 参数**的脚本（通过环境变量自动读取，无需手动传）：`audit/gift/audit.py`（非房/礼包审核）、`audit/package/audit.py`（套餐审核）、`create-fullday.py`、`create-hourly.py`、`create-poi.py`、`create-partner.py`、`create-room.py`、`query-contract.py`、`create-non-room.py`、`create-package.py`、`create-super-deal.py`、`enroll-marketing.py`

**2. 工作目录**：所有 `python3 factory/...` 命令必须在 `hotel_testdata_cli/` 子目录下执行（即 `factory/`、`scripts/` 所在的根，**不是** SKILL.md 所在的目录）。
执行任何命令前，先用 `glob_file_search` 找到本 SKILL.md 的绝对路径，取其所在目录作为 `SKILL_DIR`，然后 `cd "$SKILL_DIR/hotel_testdata_cli"` 再执行后续所有命令。例如：
```bash
cd <SKILL_DIR>/hotel_testdata_cli && ls factory/  # 应显示 fullday/ hourly/ non-room/ 等子目录
```

**3. 依赖检查**（已安装跳过）：
```bash
python3 -c "from meituan.cli.commands.du_thrift import invoke_thrift; print('OK')" 2>/dev/null \
  || pip install --upgrade mt-qa-tool -i http://pypi.sankuai.com/simple --trusted-host pypi.sankuai.com
```

**4. testdata-cli 安装检查**（数据池查询工具，已安装跳过）：
```bash
testdata-cli --version 2>/dev/null || npm install -g @cscqa/testdata-cli --registry=http://r.npm.sankuai.com
```

**5. testdata-report-execution 上报组件依赖**（执行记录上报，已安装跳过）：
```bash
bash "$SKILL_DIR/scripts/setup.sh"
```
- 已安装 → 直接跳过，无任何输出
- 未安装 → 自动执行 `mtskills i testdata-report-execution` 安装

---

## [GATE]执行记录上报（testdata-report-execution 接入）

本 Skill 接入 `testdata-report-execution` 组件，每次构造执行自动上报到 Supabase 看板。**三层防线**（pending 标记 + 开场自愈 + sweeper）保证即使 Agent 遗忘也不会丢记录。

收到用户请求后，按以下顺序执行：

0. **读取通用规则** → 本 SKILL.md 的 Anti-Pattern、初始化、场景路由等
1. **上报组件初始化** → 读取 `~/.catpaw/skills/testdata-report-execution/SKILL.md`，按其「开场自愈（第 1 层）」流程扫描 pending 标记目录并补收尾遗留记录
2. **依赖检查** → 执行上方初始化部分的所有依赖安装步骤
3. **场景判断** → 检查 query 是否含 `[DEBUG]`/`[调试]`/`--debug`（调试模式跳过全部上报）；判断是否为间接调用（nested，编排场景静默记录不 AskQuestion）
4. **识别业务类型** → 解析用户诉求，确认要构造什么（解析阶段不上报）
5. **执行上报阶段一** → 确认进入构造循环后，读取 report skill 的 `references/implementation.md`，执行 insert 获得 RECORD_ID + START_TS（脚本自动落 pending 标记，第 0 层）
6. **业务逻辑** → 读取对应 workflow / schema，执行数据构造（可能多轮交互）
7. **执行上报阶段二** → 到达终态后在回复中提及"正在记录执行结果"，执行 update 回填 detail + duration_seconds（终态时脚本自动删标记）
8. **最终回复 + 阶段三**（仅直接调用）→ AskQuestion 收集用户反馈并更新 success 字段

> 上报失败不阻塞主流程。详细操作代码模板、字段语义、多产出模型、错误路径处理均见 `testdata-report-execution` 的 `references/implementation.md`。

---

## 场景路由

两步决策，不反问用户能推断的信息：

1. **确定商品类型**：从用户描述识别目标商品，锁定对应 workflow
2. **判断 ID 持有情况**：用户未显式给出的 ID 一律视为"未提供"，直接进入 W8 对应路径自动补齐

> 未指定商品参数（早餐/取消政策等）时直接用模板默认值；未说明境内/境外时**默认按境内处理**，无需询问。

| 用户意图 | workflow | 前置 ID |
|---------|---------|--------|
| 构造全日房（含取消政策/早餐/附近专享/现付/境外多人多价） | `references/workflows/w1-create-fullday.md` | partnerId + poiId + roomId + contractNo |
| 构造钟点房 | `references/workflows/w2-create-hourly.md` | partnerId + poiId + roomId + contractNo |
| 构造非房 xGoods + 审核（只支持境内） | `references/workflows/w3-create-non-room.md` | partnerId + poiId |
| 构造套餐 + 审核（只支持境内） | `references/workflows/w4-create-package.md` | partnerId + poiId + contractId |
| 构造房转套餐（货盘规则上单，系统自动生成套餐，无需 contractId） | `references/workflows/w9-create-palletize-package.md` | partnerId + poiId + roomId |
| 构造超团（非通兑/通兑）+ 审核 | `references/workflows/w5-create-super-deal.md` | 需先按 W1 单独创建专属全日房拿 goodsId；非通兑: partnerId + poiId + goodsId；通兑: partnerId + ≥2 poiId + 对应 goodsIds |
| 营销报名 / 缓存刷新 / 改价审核 / 上线下线 | `references/workflows/w6-marketing-ops.md` | goodsId / spuId / productId 之一 |
| 开房 / 关房 / 修改库存余量 | `references/workflows/w7-inventory-ops.md` | partnerId + poiId + roomId |
| 门店私海认领 / 供应商绑定门店 / 价格模式切换 | `references/workflows/w8-infra-bootstrap.md` | poiId（认领）/ poiId+partnerId（绑定）/ platformContractId（价格模式） |
| 住宿门店资质添加（工具476）、供应商门店资质审核（工具498） | `references/workflows/w8-infra-bootstrap.md` | poiId |

**前置 ID 缺失时自动进入 W8 补齐**，根据用户实际持有情况走对应路径：

| 用户提供的信息 | 路径 | 境外时额外要求 |
|-------------|------|-------------|
| partnerId + poiId 均有 | **路径B** | 两者均须为境外实体 |
| 仅有 partnerId | **路径D** | 新建门店时加 `--overseas` |
| 仅有 poiId | **路径C** | 数据池 tag 换为`境外供应商` |
| 什么都没有 | **路径A** | 全链路加境外参数 |

→ 读 `references/workflows/w8-infra-bootstrap.md` 按对应路径执行。

> 境外全日房参数与境内完全不同（`priceSameTag` + `maxAdultAdmissibility` + `priceFactorInfos`，`priceInfo` 传 null）。详见 `w1-create-fullday.md` 的「境外多人多价」节。

---

## 失败处理（最多 2 轮重试）

1. 解析 `checkerResultItems` / `message` → 补字段重试
2. 读 `factory/<类型>/schema.json` → 补字段重试
3. 2 轮仍失败 → 输出探索报告，告知人工介入

---

## 按需加载（L3 references）

| 时机 | 行动 |
|------|------|
| 进入任意 workflow 前 | 读对应 workflow 文件（w1～w8） |
| 参数含义/枚举不确定时 | 执行 `python3 factory/<路径>/xxx.py --show-schema`（所有脚本均支持） |
| --show-schema 不够时 | 读 `factory/<类型>/schema.json` |
| 供应商参数枚举 | 读 `factory/infra/create-partner-schema.json` |
| 共用枚举值 | 读 `references/shared/enums.md` |
| RPC 字段全量 | 读 `references/goods/model.md` |
| 库存 countType 问题 | 读 `references/pitfalls/inventory.md` |
| 境外多人多价（priceSameTag / priceFactorInfos） | 读 `factory/fullday/schema.json` 的 scenario_8/9 节 |
| 供应商/contractNo/房型命名问题 | 读 `references/pitfalls/infra.md` |
| Thrift RPC 调用报错 | 读 `references/pitfalls/rpc.md` |

---

## 上报参数

| 参数 | 值 |
|------|------|
| `REPORT_TABLE` | `hotel_testdata_records` |
| `skill_name` | `hotel-product-testdata` |
| `product_type` | `fullday` / `hourly` / `non_room` / `package` / `super_deal` / `infra` / `marketing` / `inventory` |

> detail 字段结构为通用规范，定义在 `testdata-report-execution` SKILL.md 的「上报 detail 字段（通用规范）」章节中。
