# CHANGELOG — component-crash-chart

## v2.1.0 — 2026-03-31

### 新增：ANR 图表支持

- **`--type anr`**：generate_chart.py 新增 `--type` 参数（`crash`/`anr`，默认 `crash`）
  - ANR 数据通过 `crash_time_data.fault_number_time`（`type=anr`）查询，与 crash 口径一致
  - 输出文件名自动加 `-anr` 后缀，如 `raptor-android-anr-2026-03-31.png`
  - SKILL.md description / 触发词新增 ANR 相关关键词

### 修复：ANR 图表 title 未动态替换

- **问题**：`--type anr` 时，图表 title（`suptitle`/`set_title`）及分析结论文字仍显示 "Crash"
- **修复**：
  - 在 `draw_minute`、`draw_hourly`、`draw_nday`、`draw_version_compare` 函数顶部注入 `type_label`（`ANR`/`Crash`）
  - 所有 `suptitle`/`set_title` 中的字面量 "Crash" 替换为 `{type_label}`
  - `build_notify_message` 新增 `data_type` 参数，分析结论标题同步动态输出
  - 分钟级、N天趋势、版本对比的 print 标题一并修正

### 修复：当天数据不完整时环比结论不准确

- **问题**：当天数据截至 N 小时时，直接和昨天全天对比给出"环比改善/恶化"，有误导性
- **修复**：
  - 检测当天是否为"今天"（Asia/Shanghai 时区）且当前小时 < 23
  - 是则取昨天 0~N 小时（同时段）数据做对比，结论为"今日 0~Nh vs 昨日同时段"
  - 同时附全天估算值供参考
  - 当天数据完整时（历史日期 或当天已过23点），维持原有全天环比逻辑

---

## v2.0.1 — 2026-03-25

### 修复：对比日数据口径偏差

- **问题**：对比日（昨天等）之前用分钟级分段累加，与 Raptor 崩溃量存在偏差
- **修复**：对比日改用 `ONE_HOUR` 小时级查询，全天 24 小时聚合，口径与 Raptor 对齐
- **同步修复**：`_parse_data_items` 新增对 `"YYYYMMDD HH"` 格式（小时级 x 字段）的解析支持

---

## v2.0.0 — 2026-03-25

### 重构：移除 SSO/token 鉴权，改用无鉴权 MCP 接入点

**背景**：Perf MCP（meat-mcp-server，接入点 a240a999b4ca46）token 换票长期失败，
改用两个无需鉴权的接入点，数据口径更稳定。

- **数据源切换**：从 `meat-mcp-server`（需 token）→ `crash_time_data`（Friday id=1339）+ `crash_detail`（Friday id=1176）
- **删除换票逻辑**：移除 `_refresh_perf_token_if_needed()`、`sso-auth-cli` 调用、token-cache.json
- **自动注册 MCP**：`check_dependencies()` 新增自动检测并注册缺失的 MCP server，其他用户无需手动配置
- **清理旧配置**：`config/mcporter.json` 移除废弃的 `perf` 条目；删除 `token-cache.json`
- **SKILL.md / README.md**：前置依赖更新为 Friday 链接 + 接入点 + 注册命令

---

## v1.6.4 — 2026-03-24

### 优化：mis 自动读取，不再硬编码

- 换票时 mis 改为从 `~/.config/sso-auth-cli/cache.json` 自动读取
- 任何用户安装后无需修改脚本，自动使用自己的 misId

---

## v1.6.3 — 2026-03-24

### 修复：sso-auth-cli 换票 stdout 为空问题

- 根因：`sso-auth-cli` 不输出到 stdout，之前的 `r.stdout.strip()` 永远为空
- 修复：改用 `--cookie` 模式，从合并输出中用正则 `6b972edf36_ssoid=(\S+)` 提取 token
- 影响：其他用户第一次安装时可自动完成换票，无需手动操作

---

## v1.6.2 — 2026-03-24

### 优化：token 换票 CIBA 支持

- 换票逻辑升级为三级 fallback：
  1. `sso-auth-cli` 调用成功 → 直接用（CIBA 有缓存时静默换票）
  2. stdout 为空 → 等待 30s 后重试（CIBA 无缓存时 CLI 会推大象授权消息，用户点确认后可成功）
  3. 重试仍空 → 从 `sso-auth-cli` 自身 cache.json 读 CIBA token（有效期 3 天）
- 用户仅在 token 彻底失效且无任何缓存时才需要操作一次大象授权

---

## v1.6.1 — 2026-03-24

### 修复：换票兜底逻辑

- `_refresh_perf_token_if_needed()` 新增兜底：sso-auth-cli stdout 为空时，自动从 `~/.config/sso-auth-cli/cache.json` 的 `exchangedTokens.6b972edf36.ssoid` 读取完整 token

---

## v1.6.0 — 2026-03-24

### 优化：Skill 结构精简（对照 create-skill 规范）

- **[压缩] description**：从 900+ 字符压缩至 395 字符，去掉 emoji 和话术示例，保留核心 WHAT + 触发词
- **[删除] 内嵌 Changelog**：SKILL.md 中的 `## 📋 Changelog` 章节已删除，由独立 `CHANGELOG.md` 承载
- **[外置] 预设组件表**：`## 完整预设组件组` 内容移入 `references/presets.md`，SKILL.md 保留一行链接
- **[新增] 错误处理说明**：前置依赖章节补充换票失败、MCP 注册失败、S3 上传失败三种场景的处理方式

---

## v1.5.2 — 2026-03-23

### 修复：大象消息格式强制单条

- 禁止用 `media=` 单独发图（文字会丢失）
- 强制流程：S3 上传 → URL 嵌入分析文字 → 一条纯文字消息发出
- SKILL.md 第五步和回复模板均已加强制规则说明

---

## v1.5.1 — 2026-03-23

### 优化：sso-auth-cli 自动安装

- 换票前自动检测 sso-auth-cli 是否已安装（`shutil.which`）
- 未安装时自动执行 `npm install -g @dp/sso-auth-cli --registry=http://r.npm.sankuai.com`
- 新用户无需手动安装，开箱即用

---

## v1.5.0 — 2026-03-23

### 优化：换票改用 sso-auth-cli，Token 缓存延长至 3 天

**背景**：之前使用 `exchange-token.sh app` 换票，app 模式无用户权限，token 有效期短（约 80 分钟），导致频繁需要用户手动鉴权。

**改动**：
- 换票命令改为 `sso-auth-cli 6b972edf36 --mis nieyunlong`，优先命中 sso-auth-cli 自身缓存（CIBA token 3 天有效）
- `_TOKEN_TTL` 从 4800 秒（80 分钟）提升至 259200 秒（3 天）
- 删除 `_get_ssoid()` 和 `_get_exchange_cmd()` 两个辅助函数，换票逻辑更简洁
- 正常情况下每 3 天才需要用户点一次大象授权，sso-auth-cli 命中缓存时完全无感

---

## v1.4.2 — 2026-03-20

### 修复：换票改为 app 模式，彻底解决卡死问题

**根因**：之前换票传的是 mis 账号，但 exchange-token.sh 需要 ssoid（用户登录态），参数不匹配导致换票必然失败；token 为空时代码静默跳过，mcporter 无有效 token，查询全部超时卡死。另外 `input()` 在非交互环境永远阻塞也是卡死来源。

**修复**：
- 换票统一改为 `app` 模式（client_credentials），无需用户 ssoid，不依赖用户身份，不会阻塞
- 移除 `input()` 调用，彻底杜绝非交互环境阻塞
- 首次自动注册超时从 60s 缩短到 30s

---

## v1.4.1 — 2026-03-20

### 修复：mis 账号不再写死，支持多用户

- `_refresh_perf_token_if_needed()` 和首次自动注册中的换票命令，mis 账号改为动态获取：token-cache.json 缓存 → USER.md → 询问用户
- 同时修复旧路径 `friday-mcp/scripts` → `friday-catclaw-mcp/scripts`
- token-cache.json 写入时同步保存 mis_id，下次无需重新询问

---

## v1.4.0 — 2026-03-20

### 优化：Perf MCP 接入点固化 + 首次自动注册

#### 接入点写死，不再让用户手动取

- 之前：首次使用需要打开 friday.sankuai.com 页面手动取 HTTP endpoint
- 现在：接入点固定为 `http://mcphub-server.sankuai.com/mcphub-api/a240a999b4ca46`，无需任何手动操作

#### 首次安装自动换票注册

- 之前：检测到 perf 未配置时直接报错退出，用户需要手动执行 3 步接入流程
- 现在：自动调用 exchange-token.sh 换票并注册 mcporter，只有自动注册也失败时才提示手动操作

#### Token 自动刷新（已有逻辑，保持不变）

- token-cache.json 缓存 token，TTL 80 分钟
- 每次查询前自动检测过期并刷新，用户无感知

---

## v1.3.1 — 2026-03-17

- 初始版本，支持小时级 / N天趋势 / 多版本对比 / 同比四种模式
- 覆盖美团/点评/外卖，Android/iOS/HarmonyOS 三平台
