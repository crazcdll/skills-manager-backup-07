---
name: raptor-exception-investigation
description: 自动化排查美团 Raptor 前端监控平台上的 MRN/React Native 报错全流程。功能包括：自动打开 Raptor 错误详情并提取堆栈信息、通过 sourcemap API 解析源码位置、在 Diva 平台自动搜索并下载对应端（美团/大众点评/鸿蒙，iOS/Android/HarmonyOS）的 bundle 源码、自动解压并定位问题代码、输出详细的根因分析报告和修复建议、自动创建学城排查文档并归档。支持 fatal/error/warn 各级别告警，覆盖 iOS/Android/HarmonyOS 三端，涵盖 null is not an object、undefined is not a function、Network request failed 等常见错误模式。当用户提供 Raptor 错误链接、或提到「Raptor 报错」「MRN 报错」「线上 JS 错误」「bundle 报错」「排查错误」「前端告警分析」等场景时使用。
---

# Raptor 异常排查 Skill

## 概述

完整排查一条 Raptor 前端监控报错：错误详情 → sourcemap 解析 → bundle 下载 → 源码定位 → 根因分析 → 输出排查总结报告。

详细分步流程见 [references/workflow.md](references/workflow.md)。

## 计时规则（必须执行）

**开始时**：用户发送 Raptor 链接或触发排查指令的那一刻，立即用以下命令记录开始时间：

```bash
date '+%Y-%m-%d %H:%M:%S'
```

将输出结果保存为 `START_TIME`，在后续总结中使用。

**结束时**：输出根因分析结论后，再次执行 `date '+%Y-%m-%d %H:%M:%S'` 记录结束时间，保存为 `END_TIME`。

**计算耗时**：
- **真实过去时间** = END_TIME - START_TIME（总挂钟时间）
- **实际花费时间** = 真实过去时间 - 等待用户输入的时间（每次等待用户回复截图/确认，记录等待开始和结束时间，累加后从总时间中减去）

在最终排查总结中输出这两个时间。

## 关键平台

- **Raptor**：`https://raptor.mws.sankuai.com` — 前端错误监控
- **Diva**：`https://diva.sankuai.com` — MRN bundle 管理与下载

## 核心流程（速览）

1. **打开 Raptor 错误详情** → 点击 [详情] 读取堆栈、平台、App、版本信息
2. **确认关键信息**：App（美团/大众点评）、平台（iOS/Android/HarmonyOS）、bundle 名称、bundle 版本、行列号
3. **调 Raptor sourcemap API** 直接获取解析后的源码位置（优先！）
4. **去 Diva 下载 bundle**：直接导航到版本详情页 → 选择正确端 → 点击「zip 下载」
5. **查看源码**：根据 sourcemap 解析结果定位具体文件和行号
6. **根因分析 + 修复建议**

## API 优先策略（重要！）

### Step 1：用 API 获取 sourcemap 解析结果

先 navigate 到 Raptor 页面获取登录态，然后直接用 `evaluate + fetch` 调 sourcemap API，**无需 UI 操作**：

```js
// 先 navigate 到 Raptor 页面
// 然后 evaluate 执行：
const res = await fetch(
  'https://raptor.mws.sankuai.com/api/sourcemap/newget' +
  '?line={rowNum}&column={colNum}&jsUrl={jsUrlHash}'
)
const data = await res.json()
// data.data[0].source  → 源文件路径（如 node_modules/@mrn/xxx/src/utils/Foo.tsx）
// data.data[0].line    → 源码行号
// data.data[0].column  → 源码列号
// data.data[0].extraData → 源码上下文（前后几行代码）
```

**jsUrl 参数**：从 Raptor 错误详情的资源URL中提取，是 bundle 文件的 MD5 hash（不是完整 URL）。

### Step 2：用 API 搜索 Diva bundle

```js
// navigate 到 diva.sankuai.com 后 evaluate 执行：
const res = await fetch(
  'https://diva.sankuai.com/api/bundle/listOfCurrent' +
  '?keyword={bundleName}&pageIndex=1&pageSize=6'
)
const data = await res.json()
// data.data.list[0].bundleName → bundle 名称
// data.data.list[0].lastPublishVersion → 最新版本
```

### Step 3：直接导航到 Diva 版本详情页

Diva 版本详情页 URL 规律（**无需搜索 UI**）：
```
https://diva.sankuai.com/bundle/{bundleName}/versions/{version}/prod?app={app}&platform={platform}
```

App 和 Platform 参数映射：
| 错误日志中的 App | Diva app 参数 | 平台 | Diva platform 参数 |
|---|---|---|---|
| com.meituan.imeituan（美团） | `group` | iOS | `iOS` |
| com.meituan.imeituan（美团） | `group` | Android | `Android` |
| com.dianping.v1（大众点评） | `dianping` | iOS | `iOS` |
| 大众点评动态化容器(Nova) | `Nova` | HarmonyOS | `HarmonyOS` |
| 美团 HarmonyOS | `group` | HarmonyOS | `HarmonyOS` |

示例：美团 iOS 端
```
https://diva.sankuai.com/bundle/rn_hotel_hotelchannel-order-detail/versions/3.1017.662/prod?app=group&platform=iOS
```

### Step 4：获取 zip 下载链接

```js
// navigate 到版本详情页后 evaluate 执行：
Array.from(document.querySelectorAll('a'))
  .filter(el => el.innerText.includes('zip 下载'))
  .map(el => ({ text: el.innerText.trim(), href: el.href }))
```

然后用 curl 下载到工作区：
```bash
curl -L "{zip下载链接}" -o {bundleName}_{version}_{app}_{platform}.zip
unzip -o {zip文件} -d {解压目录}
```

## 重要注意事项

### 从 Raptor 错误详情提取关键字段

打开详情面板后，用 evaluate 读取所有信息：
```js
document.querySelector('.detail-modal__content').innerText
```

需要提取：
- **平台**：MRN / iOS 图标
- **User Agent**：判断 App（`com.meituan.imeituan` = 美团，`com.dianping.v1` = 大众点评）
- **资源URL**：格式 `{bundleName}/{version}/{taskId}/index.js`
- **rowNum / colNum**：sourcemap 解析用的行列号
- **堆栈信息**：若 Raptor 已解析（「解析结构」tab），直接使用源码路径

### bundle 文件可能是 Hermes 字节码

MRN bundle 的 `index.js` 通常是二进制 Hermes 字节码，无法直接阅读。优先使用 Raptor sourcemap API 的 `extraData` 字段，它直接返回源码上下文。

## 常见错误模式

**`null is not an object`（iOS）**：访问了已卸载组件的 ref 或 DOM 节点。检查定时器/异步回调中是否有 `if (!this.xxx) return` 空值判断。

**`undefined is not a function`**：方法未绑定或对象未初始化，检查调用链上的对象是否存在。

**`Network request failed`**：网络请求异常，通常不是代码 bug，关注是否有重试逻辑。

## 排查总结报告（必须输出）

根因分析完成后，**必须**按以下格式输出一份完整的排查总结报告，详细格式见 [references/summary-template.md](references/summary-template.md)。

### 创建学城文档（必须执行）

排查完成后，**必须**将排查报告保存到学城。目标目录：`https://km.sankuai.com/collabpage/2281669253`（目录 ID: `2281669253`）。

**文档标题格式**：`YYYYMMDD-错误描述`
- 其中 YYYYMMDD 使用**排查开始时的当天日期**（START_TIME 的日期部分）
- 示例：排查开始时间为 2026-03-19 01:12:17，则文档名为 `20260319-酒店订单提交失败-订单包含2张成人票`

**使用 citadel 创建文档（推荐 --file 方式）**：

```bash
# 步骤1：将排查报告保存到文件
write 工具创建文件：/Users/crazcdll07/coder/meituan-code/catpaw-desk/investigation_report.md

# 步骤2：使用 --file 参数创建文档（避免命令行长度限制和特殊字符问题）
oa-skills citadel createDocument \
  --title "YYYYMMDD-错误描述" \
  --file /Users/crazcdll07/coder/meituan-code/catpaw-desk/investigation_report.md \
  --parentId 2281669253 \
  --mis {用户MIS号}
```

**如果创建失败，按以下顺序排查**：

1. **检查 oa-skills 版本**：
   ```bash
   npm list -g @it/oa-skills --depth=0 2>/dev/null | grep oa-skills
   ```

2. **查看 citadel 帮助**：
   ```bash
   oa-skills citadel createDocument --help
   ```

3. **常见问题处理**：
   - **Node.js 版本问题**：citadel 会自动升级 Node.js 到 v18，等待完成即可
   - **MIS 号未指定**：添加 `--mis {用户MIS号}` 参数
   - **认证失败**：使用 `--force-ciba` 强制重新认证
   - **fetch is not defined**：这是已知问题，文档可能已创建成功，检查学城链接

4. **验证文档创建成功**：
   - 命令输出中包含 `✅ 文档创建成功！`
   - 记录 `文档ID` 和 `访问链接`
   - 如果看到 `fetch is not defined` 但前面有成功提示，文档通常已创建

**文档内容模板**：

```markdown
# 排查总结报告

## 基本信息
| 字段 | 值 |
|---|---|
| 项目 | {bundleName} |
| 平台 | {platform}（iOS / Android / HarmonyOS） |
| App | {app}（美团 / 大众点评） |
| App 版本 | {appVersion} |
| Bundle 版本 | {bundleVersion} |
| 错误级别 | {level}（fatal / error / warn） |
| 告警量 | {count}（时间范围内） |
| 问题发生时间 | {从 Raptor 错误详情中提取的上报时间，如 2026-03-17 00:49:33} |
| 排查时间 | {START_TIME} ~ {END_TIME} |
| 排查实际耗时 | {实际花费时间} |

## 问题概述
{一句话描述问题：什么场景下，什么组件/模块，发生了什么错误}
  
## 错误详情
- **错误名称**: {errorName}
- **错误类型**: {errorType}
- **错误代码**: {errorCode}
- **错误信息**: {errorMessage}
- **业务类型**: {bizType}

## 环境信息
- **设备**: {device}
- **系统版本**: {systemVersion}
- **MRN版本**: {mrnVersion}
- **Bundle名称**: {bundleName}
- **Bundle版本**: {bundleVersion}
- **来源页面**: {referer}
- **用户所在地**: {location}
- **网络**: {network}

## 根因
{具体根因描述}

## 修复方案
{修复方案描述，包括代码改动示例}

### HTTP 接口相关问题处理（重要！）

如果排查确定是 **HTTP 接口返回的业务错误** 或 **HTTP 接口相关问题**（如接口超时、接口返回 5xx 错误、接口返回数据格式异常等），需要执行以下步骤：

1. **获取值班人信息**：访问 https://cti.sankuai.com/rg/detail/oncall/info?rgId=218 获取当前值班人
2. **值班人提取逻辑**：
   - 默认取页面中**第一个值班人**
   - 检查该值班人是否有「已上线」标签
   - 如果有「已上线」标签，则使用该值班人
   - 如果没有「已上线」标签，则在修复方案中提供链接，让用户自己查看
3. **在修复方案中增加联系值班人**：

```
- 联系值班人「{值班人名字}」一起排查（值班人获取链接：https://cti.sankuai.com/rg/detail/oncall/info?rgId=218）
```
或者（如果没有找到已上线的值班人）：
```
- 查看当前值班人：https://cti.sankuai.com/rg/detail/oncall/info?rgId=218
```

**判断是否为 HTTP 接口相关问题的依据**：
- 错误信息来自 HTTP 响应体（如 customInfo 中的 code、message 来自接口返回）
- 错误类型为 network 相关（Network request failed、fetch error 等）
- 错误涉及接口数据解析（JSON parse error 等）

## 影响评估
{是否影响用户功能，影响范围，是否有静默失败风险}

## 排查耗时
| 指标 | 时间 |
|---|---|
| 排查开始时间 | {START_TIME} |
| 排查结束时间 | {END_TIME} |
| 真实过去时间 | {X} 分 {X} 秒 |
| 实际花费时间 | {X} 分 {X} 秒 |

## 问题发生时间
{从 Raptor 错误详情中提取的上报时间，如 2026-03-17 00:49:33}

## Raptor 链接
{Raptor错误详情链接}
```

**输出要求**：
1. 创建文档后，输出文档链接给用户
2. 确认文档创建成功（检查返回的 contentId）
3. 如果创建命令报错但显示成功信息，以成功信息为准（fetch is not defined 是已知问题）
