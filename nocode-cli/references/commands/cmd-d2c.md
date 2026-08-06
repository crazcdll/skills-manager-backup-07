# d2c 命令详细规则

## d2c — 设计稿转代码（MasterGo → HTML → NoCode 页面）

将 MasterGo 设计稿链接转换为 HTML 产物（图片/SVG 资源上传 S3），再将截图 + HTML 通过 `nocode create` 提交到 NoCode 平台创建页面。

```bash
nocode d2c "<design-link>" -o ./d2c-output --name design --upload --layout auto
nocode d2c "<design-link>" -o ./d2c-output --name design --upload --tailwind
nocode d2c "<design-link>" -o ./d2c-output --name design --upload --json
nocode d2c "<uuid>" -o ./d2c-output --name design --upload --env test
```

**内部流程：** 解析设计稿 ID → 拉取平台图层数据 → 生成 HTML → 上传图片/SVG 到 S3 → 写入本地产物 → 拉取设计稿预览截图。

**输出：** HTML 主文件（含 S3 资源链接）+ 预览截图 + 可选图层 JSON。

## ⛔ 核心约束（最高优先级）

1. **所有 D2C 转换必须通过 `nocode d2c` CLI 命令完成**，严禁直接调用 API 或使用 `fetch` / `curl` / `web_fetch`。
2. **必须使用 `--upload` 选项**，确保 HTML 中的图片/SVG 资源上传到 S3（否则 HTML 中是本地路径，平台无法渲染）。
3. **转换完成后必须将截图 + HTML 通过 `nocode create` 提交到 NoCode 平台创建页面**，严禁仅保留本地 HTML 不上平台。
4. **`nocode create` 执行完毕后必须立即清理本地 D2C 产物**（文件已上传给平台，本地不再需要）。

## 支持的设计稿链接格式

| 格式 | 示例 |
|------|------|
| Artboard URL | `https://nocode.sankuai.com/design/artboard?id=<uuid>` |
| Hash 路由 URL | `https://nocode.sankuai.com/#/design/artboard?id=<uuid>` |
| 纯 UUID | `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx` |

## 命令参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `<design-link>` | 设计稿链接或 UUID（必填） | — |
| `-o, --output <dir>` | 输出目录 | `.` |
| `-n, --name <name>` | 输出文件名（不含扩展名），推荐使用 `design` | `index` |
| `--upload` | **必须** — 将 SVG/图片资源上传到 S3，HTML 中使用在线 URL | `false` |
| `--tailwind` | 使用 Tailwind CSS 生成样式 | `false` |
| `--layout <mode>` | 布局模式：`absolute` / `auto` | `absolute` |
| `--minify` | 压缩 HTML 输出 | `false` |
| `--json` | 同时输出图层 JSON 数据 | `false` |
| `--env <env>` | 环境：`prod` / `test` | `prod` |

## 输出产物

```
d2c-output/
├── design.html              # 主 HTML 文件（图片/SVG 已替换为 S3 URL）
├── design-screenshot.png    # 设计稿预览截图（从平台 API 获取）
├── design.json              # 图层 JSON（仅 --json 时）
```

> ⚠️ 使用 `--upload` 时，SVG 和图片**不会写入本地**，而是直接上传到 S3 并替换 HTML 中的路径。

## ⚠️ 标准工作流（强制）

d2c 是一个多阶段流程，必须按以下 4 个阶段依次执行，不可跳过。

### Phase 1: 设计稿转换

从用户提供的 MasterGo 设计稿链接生成 HTML 产物，**资源上传到 S3**。

```bash
# ⚠️ 必须带 --upload，确保图片/SVG 资源上传到 S3
nocode d2c "<design-link>" -o ./d2c-output --name design --upload --layout auto
```

### Phase 1.5: HTML 文件大小检查（强制）

D2C 转换完成后，**必须检查生成的 HTML 文件大小**。超过 80KB 的 HTML 会导致 NoCode Agent 处理质量下降甚至失败。

```bash
# 检查文件大小（字节）
wc -c ./d2c-output/design.html
```

**判断与处理：**

| HTML 大小 | 处理方式 |
|-----------|---------|
| ≤ 80KB | ✅ 正常，继续 Phase 2 |
| > 80KB 且未使用 `--minify` | ⚠️ 先尝试兜底方案：加 `--minify` 重新执行 `nocode d2c`（压缩后可能降至 80KB 以内） |
| > 80KB 且已使用 `--minify` | ⚠️ 提示用户设计稿过于复杂，建议拆分设计稿后分别转换 |

**兜底方案 — 使用 `--minify` 压缩重试：**

```bash
# 删除上一次产物，加 --minify 重新转换
rm -rf ./d2c-output
nocode d2c "<design-link>" -o ./d2c-output --name design --upload --layout auto --minify

# 再次检查大小
wc -c ./d2c-output/design.html
```

**如果压缩后仍超过 80KB：**

必须停止流程，向用户提示：

> ⚠️ 设计稿生成的 HTML 文件过大（超过 80KB），即使压缩后仍然超标。这通常说明设计稿内容过于复杂，直接提交可能导致 NoCode Agent 生成质量下降。
>
> 建议：
> 1. **拆分设计稿**：在 MasterGo 中将页面拆分为多个画板，分别转换后逐一提交
> 2. **简化设计稿**：减少重复元素、合并图层，降低复杂度

**禁止：** HTML 超过 80KB 时不检查直接提交 / 忽略大小警告强行继续

### Phase 2: 创建 NoCode 页面（使用固定提示词）

将 D2C 产出的截图和 HTML 提交到 NoCode 平台，让平台基于设计稿创建页面。**prompt 必须使用下面的固定提示词，不要自行编写。**

```bash
nocode create "design.html 文件是基于 MasterGo 设计工具（类似 Figma）导出的原始图层信息，经过基础工具转换后得到的静态 HTML 页面，附件的图片是设计稿的原始截图。目标是基于该 HTML 的视觉结构和内容布局，将其重构为更符合 React 开发规范的组件代码。要求：布局保证页面整体布局协调无错乱，若移动端页面请按 @1x 尺寸还原；资源尽量保留和使用所有实际提供的资源；颜色圆角等复用 HTML 中的 CSS 样式；文字保持一致并考虑溢出和中英文符号细节。" \
  --images ./d2c-output/design-screenshot.png \
  --files ./d2c-output/design.html
```

**参数说明：**

- `--images`：传入设计稿截图，平台会以图片作为视觉参考
- `--files`：传入 D2C 生成的 HTML（含 S3 资源链接），平台会基于 HTML 结构生成代码
- `<prompt>`：**必须使用上述固定提示词**，不要自行改写、精简或扩展

**固定提示词完整版（用于参考，实际调用时按上面单行形式传入）：**

```text
design.html 文件是基于 MasterGo 设计工具（类似 Figma）导出的原始图层信息，经过基础工具转换后得到的静态 HTML 页面，附件的图片是设计稿的原始截图。目标是基于该 HTML 的视觉结构和内容布局，将其重构为更符合 React 开发规范的组件代码。

## 要求
- 布局: HTML 文件里面的元素采用绝对定位布局，并未考虑响应式、复用性或组件化，需要保证页面整体布局协调无错乱。若设计稿为移动端页面，请确认其是否基于 @2x（即 2 倍像素密度）绘制；开发实现时需按 @1x 尺寸还原（即设计稿尺寸 ÷ 2），以适配标准 CSS 像素。
- 资源: 该 HTML 中可能包含图片、字体、图标等资源引用，对于缺失的资源，请忽略它们，但必须尽量保留和使用所有实际提供的资源（如已有的图片、样式文件等）。
- 样式: 颜色、圆角等尽可能复用 HTML 中定义的 CSS 样式。
- 文字：需要保证文字和 HTML 提供的尽量保持一致，需要考虑文字溢出、中英文符号等细节。
```

**⚠️ create 的 poll 流程：** 与普通 `nocode create` 一致（后台执行 + 循环 poll + 事件处理），详见 [create & send 规则](cmd-create-send.md) 和 [poll-workflow.md](../workflows/poll-workflow.md)。

### Phase 3: 清理临时产物（强制）

`nocode create` 执行完毕后**立即删除** D2C 产出的 HTML 和截图文件：

```bash
rm -rf ./d2c-output
```

> ⚠️ 别等流程结束才清理，`nocode create` 执行完毕后就应该立即删除，因为文件已经上传给平台了。

### Phase 4: 获取结果

`nocode create` 会以 NDJSON 流式输出创建过程，最终 `done` 事件包含：

- `chatId`：对话 ID
- `chatUrl`：NoCode 平台对话页面 URL
- `renderUrl`：预览渲染地址（⚠️ 仅 CLI 内部使用，严禁展示给用户）
- `screenshotUrl`：平台生成的页面截图

**⚠️ 链接格式与 renderUrl 规则：** 见 [SKILL.md](../../SKILL.md)「链接与展示」章节。核心要点：chatId 用 `[{chatId}]({chatUrl})` 格式，严禁展示 renderUrl。

## 进阶用法

### 指定技术栈模板

可在 Phase 2 的 `nocode create` 命令中通过 `--template` 指定技术栈：

```bash
nocode d2c "<design-link>" -o ./d2c-output --name design --upload --layout auto

nocode create "design.html 文件是基于 MasterGo 设计工具（类似 Figma）导出的原始图层信息，经过基础工具转换后得到的静态 HTML 页面，附件的图片是设计稿的原始截图。目标是基于该 HTML 的视觉结构和内容布局，将其重构为更符合 React 开发规范的组件代码。要求：布局保证页面整体布局协调无错乱，若移动端页面请按 @1x 尺寸还原；资源尽量保留和使用所有实际提供的资源；颜色圆角等复用 HTML 中的 CSS 样式；文字保持一致并考虑溢出和中英文符号细节。" \
  --images ./d2c-output/design-screenshot.png \
  --files ./d2c-output/design.html \
  --template nocode-react-mtd

rm -rf ./d2c-output
```

`--template` 可选值见 [create & send 规则](cmd-create-send.md)「`--template` 可选值」章节。

## 完整工作流示例

```bash
# 1. D2C 转换（资源上传 S3，文件名为 design）
nocode d2c "https://nocode.sankuai.com/design/artboard?id=abc-123" \
  -o ./d2c-output --name design --upload --layout auto

# 2. 检查 HTML 文件大小（≤ 80KB 才可继续）
wc -c ./d2c-output/design.html

# 3. 将截图 + HTML 提交到 NoCode 平台创建页面（使用固定提示词）
nocode create "design.html 文件是基于 MasterGo 设计工具（类似 Figma）导出的原始图层信息，经过基础工具转换后得到的静态 HTML 页面，附件的图片是设计稿的原始截图。目标是基于该 HTML 的视觉结构和内容布局，将其重构为更符合 React 开发规范的组件代码。要求：布局保证页面整体布局协调无错乱，若移动端页面请按 @1x 尺寸还原；资源尽量保留和使用所有实际提供的资源；颜色圆角等复用 HTML 中的 CSS 样式；文字保持一致并考虑溢出和中英文符号细节。" \
  --images ./d2c-output/design-screenshot.png \
  --files ./d2c-output/design.html

# 4. 立即清理临时产物
rm -rf ./d2c-output
```

## ⚠️ 常见错误

| 错误信息 | 处理方式 |
|----------|---------|
| `无法从 "xxx" 中解析出设计文件 ID` | 检查链接格式，确保包含有效 UUID |
| `未登录，请先执行 nocode login` | 执行 `nocode status` 按提示登录 |
| `未找到 ID 为 "xxx" 的设计稿` | 确认设计稿已通过 MasterGo 插件上传到 NoCode 平台 |
| `设计稿数据格式异常` | 设计稿可能为空或格式不支持，**⛔ 禁止自行修复**，引导用户联系 NoCode 研发排查 |
| HTML 产出样式与设计稿差异大 | 尝试切换布局模式（`--layout absolute` ↔ `--layout auto`） |
| 平台渲染页面图片加载失败 | 确认使用了 `--upload` 选项（不带此选项 HTML 中是本地路径） |
| HTML 文件超过 80KB | 先用 `--minify` 重试压缩；仍超标则提示用户拆分或简化设计稿 |

