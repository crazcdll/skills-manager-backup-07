# fork 命令详细规则

## fork — 复制（Fork）一个作品

将一个已有的 NoCode 作品完整复制为一个新的独立作品（包含代码仓库、配置、数据库等）。

```bash
nocode fork <chatId>                    # 复制作品（独立副本）
nocode fork <chatId> --branch           # 同仓建分支（可合并回原任务）
```

**参数说明：**

| 参数 | 说明 |
|------|------|
| `<chatId>` | 要复制的原作品 ID（必填） |
| `--branch` | 同仓建分支模式，复制后可合并回原任务（可选） |

## 流程

1. **权限校验**：公开对话直接放行，私密对话需要 ADMIN/MANAGER/COLLABORATOR 权限
2. **获取原作品信息**：获取标题等元数据
3. **执行 fork**：调用后端 API 执行完整复制（代码仓库、配置、数据库等，耗时约 10~30 秒）
4. **输出结果**：返回新作品的 chatId 和访问链接

## 输出格式

**成功：**

```json
{
  "status": "success",
  "newChatId": "新作品的 chatId",
  "chatUrl": "https://nocode.sankuai.com/#/chat?pageId=新chatId",
  "title": "作品标题"
}
```

**失败（权限不足）：**

```json
{
  "status": "error",
  "error": "无权限复制该私密作品，需要 ADMIN/MANAGER/COLLABORATOR 权限"
}
```

**失败（其他错误）：**

```json
{
  "status": "error",
  "error": "错误描述"
}
```

## 两种复制模式

### 1. 独立副本（默认）

```bash
nocode fork <chatId>
```

- 创建一个完全独立的新作品
- 新作品与原作品无关联，后续修改互不影响
- 适合：基于已有作品创建新项目、备份作品

### 2. 同仓建分支（`--branch`）

```bash
nocode fork <chatId> --branch
```

- 在同一代码仓库中创建分支
- 后续可以合并回原任务
- 适合：需要在不影响原作品的情况下试验新功能，之后可能合并回去

## ⚠️ 权限说明

| 对话类型 | 权限要求 |
|---------|---------|
| 公开对话 | 无需特殊权限，任何登录用户可复制 |
| 私密对话 | 需要 ADMIN、MANAGER 或 COLLABORATOR 权限 |

## 典型使用场景

```bash
# 场景 1：复制一个公开作品作为自己的起点
nocode fork cli-abc123

# 场景 2：复制私密作品（需有权限）
nocode fork cli-private456

# 场景 3：在同仓建分支，试验新功能后可合并回原作品
nocode fork cli-abc123 --branch
```

## ⚠️ 注意事项

- fork 操作可能需要 10~30 秒，因为会复制代码仓库、配置、数据库等资源
- fork 完成后，新作品是独立的（除非使用 `--branch` 模式）
- 如果原作品有数据库，fork 会同时复制数据库结构和数据
- fork 不会复制对话历史（`withDialogHistory: false`）

## 常见错误

| 错误信息 | 处理方式 |
|---------|---------|
| `无权限复制该私密作品` | 当前用户无对应权限，需联系作品管理员添加协作权限 |
| `复制任务失败` | 可能超出配额或资源限制，引导用户联系 NoCode 研发排查 |
| `获取对话私密性失败` | 网络问题或 chatId 无效，检查 chatId 是否正确 |

