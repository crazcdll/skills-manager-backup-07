# 执行记录上报

<!-- 即贴模板：整文件复制到目标 skill 的 references/report-execution.md，改一处占位 {skill-name} 即用 -->
<!-- SKILL.md 决策流程 Step 4 ③ 指向本文件（见模板尾部"SKILL.md 接线"） -->
<!-- 字段名、CLI 参数、枚举值的大小写均为固定契约，不可改 -->

> 本文件定义本 Skill 的执行记录上报方式：每个执行了真实数据构造的调用落一条执行记录（insert + 终态 update）；纯查询不建记录。

## 安装（首次使用前）

```bash
curl -fsSL https://friday.sankuai.com/open/cli/deploy/bb8ee879-663d-49e8-bf4e-6521a8bd9af3/install.sh | bash
testdata-tool-box version   # 安装验证，输出版本号即装好
```

## 上报命令（参数名大小写固定，照抄）

```bash
# insert：第一个真实写操作前
testdata-tool-box metrics report insert \
  --user-mis <个人MIS> \
  --skill-name hotel-product-testdata \
  --user-query "<用户原始诉求>" \
  --channel personal \
  --ability <capability-map域分组括号值> \
  --detail "<本次AI处理流程记录（初始）>"
# → 返回 {"status":"ok","id":<record_id>}，保存备用

# update：成功/失败/中止/异常终态都回填（失败也报 false）
testdata-tool-box metrics report update \
  --record-id <record_id> \
  --success true \
  --duration-seconds <端到端秒数> \
  --detail "<处理流程记录终态：交付ID与回读结论 / 失败原因>"
```

## 8 个必填字段（大小写与取值口径固定）

| 字段 | CLI 参数（insert/update） | 语义 | 取值注意 |
|------|--------------------------|------|---------|
| `user_mis` | `--user-mis` | **使用 Skill 的人** | **始终个人 MIS**——群场景也写人，channel 才标群特征 |
| `skill_name` | `--skill-name` | 当前 Skill 名 | 与 skill 目录注册名一致（kebab-case 小写） |
| `user_query` | `--user-query` | 用户原始诉求 | 指令原文，不改写 |
| `success` | `--success`（update） | 执行状态 | `true` / `false` / 不传=null（未收尾）——**全小写字面量** |
| `detail` | `--detail` | AI 处理流程记录 | 自由文本叙述（insert 写初始，update 补终态） |
| `duration_seconds` | `--duration-seconds`（update） | 端到端耗时 | 秒数，含人工干预时间 |
| `ability` | `--ability` | **能力域** | capability-map「一、已支持能力清单」下 `### {中文}（{domain}）` 标题的**括号值**（如 `group-buy`）——小写连字符；**capability-map 缺失则取不到，先保 C 项** |
| `channel` | `--channel` | 群/个人特征 | 会话上下文有大象群标识（`Daxiang group_`）→ `group_assistant`；否则 `personal`；SDLC 平台自动触发 → `sdlc`——**全小写，枚举不可自造** |

## 三条铁规

1. 终态必报——**失败也 update `--success false`**（漏报失败 = 坏案例蒸发，看板未反馈/失败专区失效）
2. 只 insert 不 update 等于白报（success 停在 null 无法统计）
3. 上报失败不阻塞业务主流程（CLI 报错记 WARN 继续）

解析口径（对齐看板最小字段集合文档）：biz_line / platform 不上报（由 skill_name 从注册表推导）；ext 为系统保留勿写；resolved 由看板人工回填。

## SKILL.md 接线（复制本文件后，在 SKILL.md 做两处）

1. **决策流程 Step 4 ③**（执行流程"验证+上报"收尾步）写：
   > ③ 执行记录上报——第一个写操作前 insert、终态（含失败）update，命令与字段口径见 `references/report-execution.md`
2. 执行流程没有 Step 4 的，按规范四章补全收尾步后接线（决策路径与上报是一个改造动作的两处，不分拆）
