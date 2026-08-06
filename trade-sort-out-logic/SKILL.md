---
name: trade-sort-out-logic
description: 梳理前端代码中的业务逻辑，输出结构化报告并保存到学城文档。当用户说梳理逻辑、整理逻辑、sort out logic、梳理 XX 逻辑、分析逻辑 时触发。需要提供：梳理描述和学城文档 URL（结果将保存为该文档的子文档）。
---

# 交易前端逻辑梳理 Skill

梳理指定代码范围内的业务逻辑，生成结构化分析报告，并保存为指定学城文档的子文档。

## 必要参数

| 参数 | 说明 | 示例 |
|------|------|------|
| `scope` | 梳理范围/主题描述 | 可享权益 |
| `kmUrl` | 学城文档 URL，结果将保存为该文档的子文档 | https://km.sankuai.com/collabpage/2760458080 |
| `codePath` | 业务代码路径（可选，默认由 AI 根据 scope 自行检索） | src/pages/order-detail/rights/ |

> **缺少 `scope` 或 `kmUrl` 时向用户索取**，不要猜测。`codePath` 可选，不提供则由 AI 在项目中自行检索定位。

## 工作流程

### Phase 1：环境准备

确保 Node.js 24 可用并安装最新 oa-skills：

```bash
export NVM_DIR="$HOME/.nvm" && [ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh" && nvm use 24 && \
npm install -g @it/oa-skills@latest --registry=http://r.npm.sankuai.com
```

### Phase 2：梳理代码

直接开始梳理，无需等用户确认：

1. **定位代码**：根据用户提供的 `scope` 和 `codePath`，在项目中搜索相关代码。若未提供 `codePath`，使用 Grep/Glob/CodebaseSearch 等工具自行检索。
2. **深度阅读代码**：读取相关文件，理解业务逻辑的完整调用链路，重点关注：
   - 状态变量及其变更逻辑
   - 事件回调（onChange / onPress / onCheck / onClick 等）
   - 数据流（API 调用、store 更新、组件传参）
   - 条件分支和异常处理
   - 副作用（useEffect / watch / componentDidMount 等）

### Phase 3：生成梳理报告

整理成 Markdown 格式的报告，**报告结构不做强制限制**，以下为参考模板，能够清晰展示梳理结果即可：

```markdown
## 梳理基本信息
| 项目 | 内容 |
|------|------|
| 仓库 | <仓库名称，从项目根目录或 package.json 中获取> |
| 梳理范围 | <scope> |
| 梳理日期 | <当前日期，格式 YYYY-MM-DD> |
| 代码路径 | <codePath 或 AI 检索定位的路径> |

## 梳理范围
<!-- 明确描述梳理的边界和主题 -->

## 梳理内容
<!-- 详细说明梳理的具体对象和关注点 -->

## 详细分析
<!-- 逐步分析核心业务逻辑，可根据实际情况自由组织章节结构，例如：-->
<!-- - 关键组件/模块及其职责 -->
<!-- - 逻辑调用链路（可用流程图或分步骤说明）-->
<!-- - 状态流转 / 触发机制 / 数据传递 / 边界条件 -->

## 关键发现/结论
<!-- 总结梳理后得出的关键结论和发现 -->

## 涉及文件
<!-- 列出所有涉及的文件路径 -->
```

### Phase 4：保存到学城文档

使用 citadel skill 的文件保存流程，将报告创建为指定文档的子文档：

1. **提取 parentId**：从用户提供的 `kmUrl` 中提取 `contentId` 作为 `--parentId`。
   - `km.sankuai.com/collabpage/1234567890` → `parentId = 1234567890`

2. **将报告内容写入本地临时文件**：
   ```bash
   TMP_FILE=$(mktemp /tmp/sort-out-logic-XXXXXX.md)
   cat > "$TMP_FILE" << 'EOF'
   <报告 Markdown 内容>
   EOF
   ```

3. **创建前实时生成文档标题，避免并行 session 编号重复**：
   - **必须在调用 `createDocument` 前最后一步执行**，不要在报告生成早期缓存编号。
   - 使用 `getChildContent --contentId <parentId>` 查询父文档当前所有子文档。
   - 从子文档标题中匹配 `数字-` 前缀（正则：`^\d+-`），取最大数字 `maxNo`，新文档编号为 `maxNo + 1`。
   - 如果当前目录没有符合 `数字-` 规则的子文档，则从 `1` 开始。
   - `docTitle` 格式：`{nextNo}-{scope}-逻辑梳理-{当前日期}`，其中日期格式为 `YYYY-MM-DD`，例如：`12-可享权益-逻辑梳理-2026-07-06`。
   - 如学城 CLI 要求认证传参，追加 `--mis zhangce07`。

   ```bash
   export NVM_DIR="$HOME/.nvm" && [ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh" && nvm use 24
   CHILDREN_JSON=$(oa-skills citadel getChildContent --contentId <parentId> --mis zhangce07)
   NEXT_NO=$(printf '%s\n' "$CHILDREN_JSON" | node -e "
   let input = '';
   process.stdin.on('data', chunk => input += chunk);
   process.stdin.on('end', () => {
     const jsonStart = input.lastIndexOf('\n{');
     const jsonText = jsonStart >= 0 ? input.slice(jsonStart + 1) : input;
     let titles = [];
     try {
       titles = (JSON.parse(jsonText).children || []).map(child => child.title || '');
     } catch {
       titles = [...input.matchAll(/\"title\"\\s*:\\s*\"([^\"]+)\"/g)].map(match => match[1]);
     }
     const maxNo = titles.reduce((max, title) => {
       const match = String(title).match(/^(\d+)-/);
       return match ? Math.max(max, Number(match[1])) : max;
     }, 0);
     process.stdout.write(String(maxNo + 1));
   });
   ")
   docTitle="${NEXT_NO}-<scope>-逻辑梳理-$(date +%F)"
   ```

4. **创建学城文档子文档（使用 --file 参数）**：
   ```bash
   export NVM_DIR="$HOME/.nvm" && [ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh" && nvm use 24 && \
   oa-skills citadel createDocument --title "$docTitle" --file "$TMP_FILE" --parentId <parentId> --mis zhangce07
   ```

5. **清理临时文件**：
   ```bash
   rm -f "$TMP_FILE"
   ```

### Phase 5：输出结果

向用户汇报：
- 梳理结果摘要
- 学城文档链接：`https://km.sankuai.com/collabpage/<newContentId>`
- 涉及文件数量统计

## 注意事项

1. **Node 版本**：所有 `oa-skills` 命令必须在 Node 24 环境下执行。
3. **学城文件保存**：内容较长的报告必须使用 `--file` 参数通过临时文件传递内容，避免命令行参数过长导致截断。
4. **child doc**：结果保存为指定学城文档的**子文档**，通过 `--parentId` 指定父文档。
5. **代码搜索**：若用户未提供 `codePath`，需在项目根目录下使用 Grep、Glob、CodebaseSearch 等工具自行检索相关代码，不要依赖用户提供精确路径。
6. **引用代码**：报告中引用代码时使用代码块格式，标注文件路径和行号范围。
7. **--mis 参数**：如学城 CLI 要求认证传参，确保传递 `--mis` 参数（从已有 Skill 如 trade-page-modal-audit 的模式看，当前环境应该能通过 SSO 自动处理认证，若创建失败可尝试追加 `--mis <你的mis号>`）。
