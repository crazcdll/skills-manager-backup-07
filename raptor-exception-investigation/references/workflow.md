# Raptor 报错排查详细流程

## Step 0：记录开始时间

**立即**执行，不得跳过：

```bash
date '+%Y-%m-%d %H:%M:%S'
```

将输出保存为 `START_TIME`（例：`2026-03-18 11:28:30`）。

---

## Step 1：打开 Raptor 错误详情

用 `browser_action` 导航到用户提供的 Raptor 链接，截图确认页面加载成功。

点击列表中的 **[详情]** 按钮打开右侧详情面板：

```js
// 点击第一条记录的详情按钮
document.querySelector('span.link').click()
```

等待面板加载后，读取全部内容：

```js
document.querySelector('.detail-modal__content').innerText
```

## Step 2：提取关键信息

从详情面板文本中提取以下字段：

| 字段 | 来源 | 示例 |
|------|------|------|
| 平台 | 面板顶部图标 | MRN / iOS |
| App | User Agent 中的包名 | com.meituan.imeituan → 美团 |
| 系统 | User Agent | iOS 17.5.1 |
| bundle 名 | 资源URL 第一段 | rn_hotel_hotelchannel-order-detail |
| bundle 版本 | 资源URL 第二段 / bundleVersion | 3.1017.662 |
| rowNum | 基本信息区域 | 437 |
| colNum | 基本信息区域 | 1336 |
| jsUrl hash | 资源URL 第三段（taskId）| 1773141299250（需转换为 MD5） |
| 堆栈 | 「解析结构」→「原始堆栈」| VisibilitySensor.tsx line 104:13 |

**从资源URL解析 bundle 信息：**
```
rn_hotel_hotelchannel-order-detail/3.1017.662/1773141299250/index.js
→ bundleName: rn_hotel_hotelchannel-order-detail
→ version: 3.1017.662
→ taskId: 1773141299250
```

**User Agent 解析 App：**
- `com.meituan.imeituan` → 美团（Diva app=`group`）
- `com.dianping.v1` → 大众点评（Diva app=`dianping`）

## Step 3：调 Raptor sourcemap API（优先！）

若 Raptor 已显示解析后的源码堆栈（「解析结构」tab 下有文件路径），直接使用，跳到 Step 5。

若需要手动解析，先 navigate 到 Raptor 页面，然后 evaluate 调 API：

```js
// 参数说明：
// line: rowNum（可以是逗号分隔的多个行号，对应堆栈每一帧）
// column: colNum（对应每一帧的列号）
// jsUrl: bundle 文件的 MD5 hash（从 Raptor 错误详情的 jsUrl 字段获取）

const res = await fetch(
  `https://raptor.mws.sankuai.com/api/sourcemap/newget?line=${rowNum}&column=${colNum}&jsUrl=${jsUrlHash}`
)
const data = await res.json()
console.log(JSON.stringify(data.data[0], null, 2))
```

**响应结构：**
```json
{
  "source": "node_modules/@mrn/hoteltravel-common/src/utils/VisibilitySensor.tsx",
  "line": 104,
  "column": 13,
  "name": "view",
  "functionName": "check",
  "extraData": [
    { "line": 102, "data": "    check = () => {" },
    { "line": 103, "data": "        const { burnAfterVisible, isUploadOnce } = this.props" },
    { "line": 104, "data": "        this.view.measure((ox, oy, width, height, pageX, pageY) => {" }
  ]
}
```

`extraData` 直接包含源码上下文，**通常无需再下载 bundle**！

## Step 4：去 Diva 下载 bundle 源码

若 sourcemap 解析结果不够（如需要查看更多上下文），再下载 bundle。

### 4.1 直接导航到版本详情页（无需搜索 UI）

URL 规律：
```
https://diva.sankuai.com/bundle/{bundleName}/versions/{version}/prod?app={app}&platform={platform}
```

App/Platform 参数对照：
| 错误日志 App | Diva app | 平台 | Diva platform |
|---|---|---|---|
| com.meituan.imeituan | `group` | iOS | `iOS` |
| com.meituan.imeituan | `group` | Android | `Android` |
| com.meituan.imeituan | `group` | HarmonyOS | `HarmonyOS` |
| com.dianping.v1 | `dianping` | iOS | `iOS` |
| com.dianping.v1 | `dianping` | Android | `Android` |
| Nova（大众点评动态化容器） | `Nova` | HarmonyOS | `HarmonyOS` |
| Nova（大众点评动态化容器） | `Nova` | iOS | `iOS` |
| Nova（大众点评动态化容器） | `Nova` | Android | `Android` |

示例（美团 iOS）：
```
https://diva.sankuai.com/bundle/rn_hotel_hotelchannel-order-detail/versions/3.1017.662/prod?app=group&platform=iOS
```

### 4.2 获取 zip 下载链接

```js
// navigate 到版本详情页后 evaluate 执行：
Array.from(document.querySelectorAll('a'))
  .filter(el => el.innerText.includes('zip 下载'))
  .map(el => ({ text: el.innerText.trim(), href: el.href }))
```

### 4.3 下载并解压

```bash
curl -L "{zip下载链接}" -o {bundleName}_{version}_{app}_{platform}.zip
unzip -o {zip文件} -d {解压目录}
```

**注意**：MRN bundle 的 `index.js` 通常是 Hermes 字节码（二进制），无法直接阅读。优先使用 sourcemap API 的 `extraData`。

## Step 5：查看源文件

根据 sourcemap 解析出的文件路径，通过以下方式获取源码：

1. **用户直接提供**：请用户粘贴对应文件内容（最快）
2. **本地 node_modules**：在项目目录中查找
   ```bash
   find /path/to/project -name "VisibilitySensor.tsx" 2>/dev/null
   ```
3. **内部代码平台**：访问 `https://code.sankuai.com` 搜索对应仓库

重点查看 sourcemap 指向的**具体行号**及其上下文（前后各 20 行）。

## Step 6：根因分析与修复建议

### 常见根因模式

**模式一：null 引用（最常见，iOS `null is not an object`）**
- 原因：组件卸载后，定时器/异步回调仍在执行，访问了已置为 null 的 ref
- 修复：在访问前加空值判断
  ```tsx
  check = () => {
    if (!this.view) return  // ← 加这一行
    this.view.measure(...)
  }
  ```

**模式二：定时器未清理**
- 原因：`componentWillUnmount` 中未清理 `setInterval` / `setTimeout`
- 修复：在 unmount 时调用 `clearInterval` / `clearTimeout`

**模式三：异步竞态**
- 原因：异步操作（fetch/setTimeout）返回时组件已卸载
- 修复：使用 `isMounted` 标志或 `AbortController`

### 输出格式

给出根因分析时，包含：
1. **错误根源**：具体是哪行代码、什么原因
2. **触发路径**：完整调用链说明（从堆栈还原）
3. **修复方案**：具体代码改动，优先给最小改动方案
4. **影响评估**：当前影响范围（错误量、用户数）

---

## Step 7：记录结束时间并输出总结报告

### 7.1 记录结束时间

```bash
date '+%Y-%m-%d %H:%M:%S'
```

将输出保存为 `END_TIME`。

### 7.2 计算耗时

用 Python 自动计算：

```bash
python3 -c "
from datetime import datetime
start = datetime.strptime('${START_TIME}', '%Y-%m-%d %H:%M:%S')
end = datetime.strptime('${END_TIME}', '%Y-%m-%d %H:%M:%S')
total = int((end - start).total_seconds())
print(f'真实过去时间：{total // 60} 分 {total % 60} 秒')
"
```

对于实际花费时间：将每次等待用户回复截图/确认的时间段累加，从总时间中减去。如果没有等待期，则实际花费时间 = 真实过去时间。

### 7.3 输出排查总结报告

按照 [references/summary-template.md](summary-template.md) 中的模板输出完整总结报告。
