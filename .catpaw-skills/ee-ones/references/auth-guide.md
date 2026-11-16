# 认证与故障排除指南

> **加载时机**：当遇到认证失败（401）、Token 过期、登录问题，或需要了解认证原理时，读取本文件。

---

## 认证策略概览

**默策略：先执行，按需认证。** token 通常已缓存，Agent 应直接执行目标命令，不要在每次执行前主动走认证步骤。

本工具支持多种认证方式，按以下优先级自动选择：

| 优先级 | 认证方式 | 适用场景 | 说明 |
|--------|---------|---------|------|
| 0 | **MOA 无感登录** | CatClaw/CatPaw/CatDesk/Sandbox/1024 等平台 | `ones sso login --moa --mis <MIS号>` 完全自动、非交互式，`--mis` 必传（`--catclaw` 为向后兼容别名） |
| 1 | **环境变量** | CI/CD、定时任务 | 设置 `ONES_ACCESS_TOKEN` 和 `ONES_OPERATOR`，无需交互登录 |
| 2 | **SSO 登录** | 本地开发 | `ones sso login --ciba --mis <MIS号>` 或 `ones sso login` |
| 3 | **CatPaw 降级** | CatPaw IDE 环境 | 自动从 CatPaw 本地配置读取 Token，无需显式登录 |

### 1. 环境变量（CI/CD 推荐）

无需登录，直接设置环境变量即可：

| 环境变量 | 是否必填 | 说明 |
|---------|---------|------|
| `ONES_ACCESS_TOKEN` | ✅ 必填 | SSO 访问令牌 |
| `ONES_OPERATOR` | ✖ 选填 | 操作人 MIS 号 |

```bash
export ONES_ACCESS_TOKEN="your-access-token"
export ONES_OPERATOR="your-mis"          # 可选
ones q -i 12345                           # 直接使用
```

### 0. MOA 无感登录（多平台首选）

```
ones sso login --moa --mis <MIS号>
    ↓
检测 MOA 无感登录环境（mtsso-moa-feature-probe）
    ↓
检测并安装依赖 @mtfe/mtsso-auth-official
    ↓
通过 mtsso-moa-local-exchange 获取 audience=meituan.ee.ones.fe 的 token
    ↓
直接用于 ONES API 请求（Cookie 鉴权）
```

**适用平台**：CatClaw/大象个人助理、CatPaw（含 IDE 插件）、CatPaw 云端 Agent、CatPaw CLI、CatDesk、Sandbox、1024、Friday 应用工厂 Agent

**重要**：MOA 无感登录通常能从 JWT 中自动提取用户 MIS 号，但建议显式传入 `--mis` 参数确保准确性。登录成功后 MIS 号会写入 `ones config` 中。

**获取 MIS 号的方式**（按优先级）：
1. 从 `ones config` 中读取已保存的 `operator` 字段
2. 从沙箱环境上下文获取（如 `USER.md` 或环境变量 `ONES_OPERATOR`）
3. 直接询问用户

**环境额外依赖**：MOA 无感登录依赖 `@mtfe/mtsso-auth-official`，CLI 会自动检测并安装。若自动安装失败，手动执行：
```bash
npm install @mtfe/mtsso-auth-official@latest --registry=http://r.npm.sankuai.com
```

**向后兼容**：`--catclaw` 参数保留为 `--moa` 的别名，效果完全相同。

### 2. SSO 登录（本地开发）

```
ones sso login [--ciba]
    ↓
获取 ONES FE token（audience=meituan.ee.ones.fe，48h 内免登录）
    ↓
直接用于 ONES API 请求（Cookie 鉴权）
```

#### SSO 登录方式

| 方式 | 命令 | 说明 |
|------|------|------|
| MOA 无感登录（多平台首选） | `ones sso login --moa --mis <MIS号>` | 完全自动、非交互式，`--mis` 必传（`--catclaw` 为兼容别名） |
| CIBA | `ones sso login --ciba --mis <MIS号> --force` | 命令行发起，`--mis` 跳过交互输入，`--force` 跳过重新登录确认，大象 App 确认 |
| CIBA（交互式） | `ones sso login --ciba` | 不知道 MIS 号时交互式输入（Agent 场景应避免） |
| 浏览器 SSO | `ones sso login --browser --force` | 自动打开浏览器完成 SSO，`--force` 跳过重新登录确认 |
| 手动粘贴 Token | `ones sso login --manual` | **终极兜底**，用户从浏览器复制 Token 粘贴 |

#### Token 时效

| Token 类型 | 实际有效期 | CLI 本地阈值 | 刷新方式 |
|-----------|-----------|------------|---------|
| SSO access token | **72 小时**（3 天，SSO 服务端） | 48 小时（留 24h 余量） | `ones sso refresh` |

> **48h 内无需二次确认登录**：CIBA 获取的 access token 在 SSO 服务端实际有效 72 小时，CLI 本地在 48h 处判定过期并提示刷新，留足安全余量。

#### 认证头/Cookie

- ONES 系统使用 **Cookie 认证**：`Cookie: ssoid=...; meituan.ee.ones.fe_ssoid=...`

#### Token 存储位置

- macOS: `~/Library/Preferences/ones-cli-nodejs/config.json`
- Linux: `~/.config/ones-cli-nodejs/config.json`

### 3. CatPaw 降级认证

未显式登录时，CLI 会按以下顺序自动从本地配置文件读取 Token（仅支持生产环境）：

| 优先级 | 路径 | 读取字段 | 适用场景 |
|--------|------|---------|---------|
| 1 | `~/.catpaw/sso_config.json` | `ssoid` | CatPaw 2026.2.2+ |
| 2 | `~/.catpaw/settings.json` | cookie 中的 `_ssoid` | CatPaw 旧版本 |
| 3 | `/root/nocode_task/.secret/sso.json` | `nocode` | NoCode Task 容器化场景 |

> **说明**：降级认证是静默的，只要上述文件存在且包含有效 Token，CLI 会自动使用，无需任何配置。

---

## 常见认证问题

| 症状 | 原因 | 解决方案 |
|------|------|---------|
| `command not found: ones` | 未安装 CLI | `npm i -g @ee/ones-cli --registry=http://r.npm.sankuai.com` |
| 401 / 认证失败 | Token 过期或无效 | 按顺序尝试：① `ones sso login --moa --mis <MIS>` → ② `ones sso refresh` → ③ `ones sso login --ciba --mis <MIS> --force` → ④ `ones sso login --browser --force` → ⑤ 提示用户 `ones sso login --manual` |
| `Token 已过期` 提示 | SSO Token 超过 48 小时（本地阈值，实际 72h 有效） | 同上，按顺序尝试 moa → refresh → ciba --force → browser --force → manual |
| MOA 无感登录失败 | 不在支持 MOA 的环境或依赖未安装 | 确认在支持的平台中（CatClaw/CatPaw/CatDesk/Sandbox/1024），执行 `npm install @mtfe/mtsso-auth-official@latest --registry=http://r.npm.sankuai.com` |
| CIBA 超时无响应 | 大象 App 未确认或网络问题 | 检查大象 App 推送，或换用 `ones sso login --browser --force`（浏览器方式） |
| 未找到有效认证信息 | 未登录且无降级源 | 确认 CatPaw 已登录或执行 `ones sso login --moa --mis <MIS>` |

---

## 常见操作问题

| 问题 | 解决 |
|------|------|
| 不知道空间 ID | `ones sp -n "关键词"` 搜索，或从 ONES URL `/project/48465/` 提取 |
| 不知道命令参数 | `ones <命令> --help` |
| 删除不可恢复 | 所有 delete 操作不可撤销，务必先确认 |
| 子类型更新报错 | 子类型只能更新为相同工作项类型下的合法子类型 |
| 工时记录 ID 怎么获取 | `ones wtd -i <工作项ID>` 查询工时日志 |
| 工时校验不通过 | 检查空间是否要求填写投入类型，或日期是否在允许范围内 |
| 迭代查询返回空 | 确认空间 ID 正确，且空间内已创建迭代 |
| 迭代创建失败 | 开始日期不能晚于结束日期，格式须为 YYYY-MM-DD |
| 测试计划搜索无结果 | 确认空间 ID，可用 `--no-interactive` 跳过筛选 |
| 提测状态无可流转选项 | 当前提测单可能已是终态，或用户无权限 |
| 空间查询返回空 | 确认登录状态正常，尝试 `--no-interactive` |
| 评论查询失败 | 确认空间 ID、工作项 ID 和类型参数正确 |

---

## 参考资源

- CIBA 认证文档：https://km.sankuai.com/collabpage/2732221228
- ONES API 文档：https://s3plus-bj02.vip.sankuai.com/supabase-bucket/ones-api-skill.md
- 内部 npm 源：http://r.npm.sankuai.com

