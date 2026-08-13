# 物料 ID 查询

DUO 页面协议中 `node('Name','物料ID')` 的第二个参数是**物料在资产平台注册的物料 ID**（`materialId`），**绝对禁止编造**。本页说明如何获取真实物料 ID。

## 一、首选方式：duo yooz-read-detail

**命令**：`duo yooz-read-detail`

**功能**：按物料名称（npm 包名）查询物料详情，返回中包含 `materialId`（即 `node('Name','物料ID')` 用的物料 ID）。

**用法**：
```bash
# 查询单个物料
duo yooz-read-detail -n @max/leez-button

# 批量查询（逗号分隔）
duo yooz-read-detail -n @max/leez-button,@meishi/common-layout-top-bottom

# 测试环境
duo yooz-read-detail -n @max/leez-button -e test
```

- 参数：`--names` / `-n`（必填，物料名多个用逗号分隔），`--env` / `-e`（test/prod，默认 prod）
- 接口：`POST /node/api/material/detailForMcp`
- 返回：物料详情 JSON，其中 `materialInfo.materialId` 就是协议中用的物料 ID
- 支持 lowCode 和 proCode 两种物料形态
- 版本要求：`@meishi/duo-cli >= 0.4.49`

**示例（伪返回）**：
```json
{
  "materialInfo": { "materialId": "7", "name": "LayoutTopBottom", ... },
  "config": { "type": "NORMAL_MODULE", "props": [...], "events": {...} }
}
```

## 二、其它来源（按优先级）

1. **当前页面现有协议**：已有节点引用的物料 ID 最可信，直接复用
2. **componentsMap**：页面协议里已配置的物料映射，key 就是 materialId
3. **duo yooz-read-detail**：按名称查物料详情拿 materialId（见上）
4. **物料平台/配置平台**：查物料列表

## 三、禁止行为

- ❌ 凭空编造物料 ID
- ❌ 凭印象/记忆写物料 ID和版本（会变）
- ❌ 套用其它物料的 ID（如把 LayoutTopBottom 的 `7` 用到别的节点）
- ❌ 用 npm 包名当物料 ID 写进协议

## 四、验证

1. 新增节点引用的物料，**必须在 componentsMap / dependencies 中有记录**
2. 确认物料类型（component/logic）与节点用途匹配（logic → HANDLER_MODULE/逻辑节点）
3. 确认发布版本已在页面可用

## 五、常见物料名（npm 包名，查到后需按名称查物料 ID）

- 视图类：`@max/leez-card`、`@max/leez-text`、`@max/leez-button`、`@max/leez-text-button`、`@max/leez-tip`、`@max/leez-price`、`@max/leez-tag`、`@max/leez-stepper`、`@max/leez-navigation-bar`、`@meishi/common-layout-top-bottom`、`@meishi/common-ele-line`
- 逻辑类：`@meishi/common-duo-lifecycle`
- 静态类：`@meishi/common-duo-params`、`@hfe/hotel-submit-loading-fill`

## 六、查询不到时

1. 降级查 componentsMap
2. 仍无 → 提示用户确认物料是否已发布到资产平台
3. 阻塞处理，**禁止编造 ID 硬写进协议**
