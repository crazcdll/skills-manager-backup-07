---
name: imd-design-fetch
description: 从 imd.sankuai.com 设计稿中同时提取指定节点的 DSL JSON 数据和 PNG 截图。给定设计稿链接（含 file_id、page_id、layer_id），通过 MasterGo MCP 获取 DSL JSON，通过真实 Chrome CDP + window.mg.exportAsync 获取节点截图，输出到本地文件。触发词：提取节点、获取设计稿数据、imd 节点截图、设计稿 JSON、节点导出。

---

# imd 节点数据提取（DSL JSON + PNG 截图）

给定一个 imd.sankuai.com 链接（含 `file_id`、`page_id`、`layer_id`），同时获取：
1. **DSL JSON**：通过 `mcp__mastergo-magic-mcp__mcp__getDsl` 调用
2. **PNG 截图**：通过真实 Chrome CDP（port 9222）注入 `exportAsync()` 触发下载，再 mv 到 `/tmp/`

---

## 步骤 0：解析 URL 参数并前置校验（MUST，先于任何数据获取执行）

从用户提供的 URL 中提取三个参数：

| 参数 | URL 位置 | 示例 |
|------|---------|------|
| `fileId` | 路径 `/file/{fileId}` | `165353219261284` |
| `pageId` | query `page_id=` | `598:13210` |
| `layerId` | query `layer_id=` | `956:17207` |

注意：URL 中的 `%3A` 需 decode 为 `:`。

### 前置校验规则（MUST）

在执行任何 DSL/截图获取动作前，必须先完成以下校验：

1. 依次尝试从 URL 中解析 `fileId`、`pageId`、`layerId` 三个参数
2. **三者缺一不可**：只要有任意一个参数缺失、为空或解析失败，**立即停止执行**，不得调用 MCP 或 Chrome CDP，也不得凭空猜测缺失的参数值
3. 停止后向用户汇报链接错误，需明确指出缺失的具体参数，例如：
   > ⚠️ imd 视觉稿链接格式不正确：缺少 `layer_id` 参数。请提供包含 `file_id`（路径）、`page_id`、`layer_id`（query）三个参数的完整 imd.sankuai.com 链接后重试。
4. 三个参数均存在时才可继续派生文件名变量并进入步骤 1

### 文件级/页面级链接识别（MUST，`layerId` 缺失场景的专项说明）

当校验发现**只能解析出 `fileId`、`pageId`，缺少 `layerId`** 时，典型形如：

```
https://imd.sankuai.com/ file / <fileId> ?fileOpenFrom=home&page_id=<pageId>
```

- 这类链接仅定位到**文件（file）或页面（page）层级**，代表的是**一整套包含多张视觉稿（多个 layer/节点）的设计文件**，而非某一张具体视觉稿
- 由于缺少 `layerId`，**无法从这套设计数据中确定需要分析的具体视觉稿节点**，属于第 2 条校验规则中“参数缺失”的一种典型场景，判定结论一致：**立即停止执行**，不得调用 MCP 或 Chrome CDP 获取数据，也不得猜测或遍历文件下的某个节点
- 停止后必须向用户提问澄清，明确说明链接层级问题，例如：
  > ⚠️ 检测到的链接 `https://imd.sankuai.com/ file / <fileId> ?fileOpenFrom=home&page_id=<pageId>` 只定位到**文件/页面层级**（缺少 `layer_id` 参数），这是一套包含多张视觉稿的设计文件，无法确定需要分析的具体视觉稿页面。请在 imd 中打开具体需要分析的视觉稿节点，复制包含 `layer_id` 参数的完整节点链接后重试。
- 若需求文档中同时存在多个链接，需**逐一校验**，缺少 `layerId` 的文件级链接与完整的三参数链接分别识别，不得因文档中存在其他合法链接而忽略文件级链接的错误

派生文件名变量（`:` 替换为 `-`）：
- `LAYER_SAFE` = `956-17207`
- DSL 输出路径：`/tmp/956-17207_dsl.json`
- PNG 输出路径：`/tmp/956-17207_node.png`

---

## 步骤 1：并发执行两路数据获取

### 路线 A：通过 MCP 获取 DSL JSON

调用 `mcp__mastergo-magic-mcp__mcp__getDsl`，传入 `fileId` 和 `layerId`：

```
tool: mcp__mastergo-magic-mcp__mcp__getDsl
params:
  fileId: <fileId>
  layerId: <layerId>
```

将返回的 DSL JSON 保存到 `/tmp/<LAYER_SAFE>_dsl.json`。

---

### 路线 B：通过真实 Chrome CDP 获取 PNG 截图

核心原理：使用已登录的真实 Chrome 浏览器，通过 `--remote-debugging-port=9222` 开启 CDP，
连接后向 imd 页面注入 `window.mg.exportAsync()` 脚本，触发 PNG 下载到 `~/Downloads/`。

#### B-0：启动带 CDP 的 Chrome 实例

检查 9222 端口是否已有 Chrome 监听：

```bash
curl -s --max-time 2 http://127.0.0.1:9222/json/version 2>/dev/null | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('Browser',''))" 2>/dev/null || echo "no_response"
```

若输出 `no_response`，则启动一个独立 profile 的 Chrome 实例（不影响现有 Chrome 会话）：

```bash
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
  --remote-debugging-port=9222 \
  --user-data-dir=/tmp/chrome-debug-profile \
  --no-first-run \
  "<原始 URL>" \
  > /tmp/chrome-debug.log 2>&1 &
sleep 3
curl -s http://127.0.0.1:9222/json/version | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('Browser',''))"
```

> **说明**：`/tmp/chrome-debug-profile` 是独立的 profile 目录，Chrome 会复用系统级登录态（SSO cookie），
> imd.sankuai.com 通常可直接访问无需额外登录。

#### B-1：获取 imd 页面的 WebSocket 调试地址

```bash
node -e "
const http = require('http');
http.get('http://127.0.0.1:9222/json', (res) => {
  let data = '';
  res.on('data', d => data += d);
  res.on('end', () => {
    const pages = JSON.parse(data);
    const page = pages.find(p => p.type === 'page');
    console.log(page ? page.url : 'no_page');
  });
});
" 2>&1
```

若页面 URL 不是 imd 设计稿，通过 CDP 导航：

```bash
node -e "
const http = require('http');
const { WebSocket } = require('ws');
http.get('http://127.0.0.1:9222/json', (res) => {
  let data = '';
  res.on('data', d => data += d);
  res.on('end', () => {
    const pages = JSON.parse(data);
    const page = pages.find(p => p.type === 'page');
    const ws = new WebSocket(page.webSocketDebuggerUrl);
    ws.on('open', () => {
      ws.send(JSON.stringify({id:1, method:'Page.navigate', params:{url:'<原始 URL>'}}));
      setTimeout(() => ws.close(), 2000);
    });
    ws.on('message', m => console.log(m.toString().slice(0,200)));
  });
});
" 2>&1
```

#### B-2：等待 `window.mg` 就绪

```bash
sleep 6
node -e "
const http = require('http');
const { WebSocket } = require('ws');
http.get('http://127.0.0.1:9222/json', (res) => {
  let data = '';
  res.on('data', d => data += d);
  res.on('end', () => {
    const pages = JSON.parse(data);
    const page = pages.find(p => p.type === 'page');
    const ws = new WebSocket(page.webSocketDebuggerUrl);
    ws.on('open', () => {
      ws.send(JSON.stringify({id:1, method:'Runtime.evaluate', params:{expression:'typeof window.mg !== \"undefined\" ? \"ready\" : \"not_ready\"'}}));
    });
    ws.on('message', m => {
      const r = JSON.parse(m);
      if (r.id === 1) { console.log(r.result?.result?.value); ws.close(); }
    });
  });
});
" 2>&1
```

若返回 `not_ready`，再 sleep 5 秒重试。超过 30 秒仍未就绪则提示用户检查网络或登录状态。

#### B-3：注入 exportAsync 导出 PNG

```bash
node -e "
const http = require('http');
const { WebSocket } = require('ws');
http.get('http://127.0.0.1:9222/json', (res) => {
  let data = '';
  res.on('data', d => data += d);
  res.on('end', () => {
    const pages = JSON.parse(data);
    const page = pages.find(p => p.type === 'page');
    const ws = new WebSocket(page.webSocketDebuggerUrl);
    ws.on('open', () => {
      const script = \`
        (function() {
          function findNode(node, id) {
            if (!node) return null;
            if (node.id === id) return node;
            if (node.children) {
              for (var i = 0; i < node.children.length; i++) {
                var r = findNode(node.children[i], id);
                if (r) return r;
              }
            }
            return null;
          }
          var page = window.mg.document.children.find(function(p) { return p.id === 'PAGE_ID'; });
          if (!page) return 'error: page not found';
          var node = findNode(page, 'LAYER_ID');
          if (!node) return 'error: node not found';
          window._exportDone = null;
          window._exportError = null;
          node.exportAsync({ format: 'PNG', constraint: { type: 'SCALE', value: 2 } })
            .then(function(bytes) {
              var blob = new Blob([bytes], { type: 'image/png' });
              var url = URL.createObjectURL(blob);
              var a = document.createElement('a');
              a.href = url;
              a.download = 'LAYER_SAFE_node.png';
              document.body.appendChild(a);
              a.click();
              document.body.removeChild(a);
              URL.revokeObjectURL(url);
              window._exportDone = 'LAYER_SAFE_node.png';
            })
            .catch(function(e) { window._exportError = e.toString(); });
          return 'exporting';
        })()
      \`;
      ws.send(JSON.stringify({id:1, method:'Runtime.evaluate', params:{expression: script}}));
    });
    ws.on('message', m => {
      const r = JSON.parse(m);
      if (r.id === 1) { console.log('result:', r.result?.result?.value); ws.close(); }
    });
  });
});
" 2>&1
```

将脚本中的 `PAGE_ID`、`LAYER_ID`、`LAYER_SAFE` 替换为实际值后执行。

#### B-4：等待下载完成并轮询结果

```bash
sleep 5
node -e "
const http = require('http');
const { WebSocket } = require('ws');
http.get('http://127.0.0.1:9222/json', (res) => {
  let data = '';
  res.on('data', d => data += d);
  res.on('end', () => {
    const pages = JSON.parse(data);
    const page = pages.find(p => p.type === 'page');
    const ws = new WebSocket(page.webSocketDebuggerUrl);
    ws.on('open', () => {
      ws.send(JSON.stringify({id:1, method:'Runtime.evaluate', params:{expression:'window._exportError ? (\"error: \" + window._exportError) : window._exportDone ? (\"done: \" + window._exportDone) : \"pending\"'}}));
    });
    ws.on('message', m => {
      const r = JSON.parse(m);
      if (r.id === 1) { console.log(r.result?.result?.value); ws.close(); }
    });
  });
});
" 2>&1
```

若返回 `pending`，再 sleep 3 秒重试一次。

#### B-5：将下载文件移动到 `/tmp/`

```bash
mv ~/Downloads/<LAYER_SAFE>_node.png /tmp/<LAYER_SAFE>_node.png
ls -lh /tmp/<LAYER_SAFE>_node.png
```

---

## 步骤 2：输出结果

两路数据获取完成后汇报，并用 Read tool 读取 PNG 展示截图：

```
✅ DSL JSON  → /tmp/<LAYER_SAFE>_dsl.json  (<大小>)
✅ PNG 截图  → /tmp/<LAYER_SAFE>_node.png  (<大小>, 2x 分辨率)
节点名称：<node.name>
```

---

## 前置依赖

### 路线 A（DSL）依赖：mastergo-magic-mcp

DSL 获取依赖 `mastergo-magic-mcp` MCP Server，**需要手动安装配置**，截图路线（路线 B）不依赖此 MCP。

**安装方式**：在 Claude Code 中运行以下命令添加 MCP：

```
/mcp add mastergo-magic-mcp
```

或者手动编辑 `~/.claude/settings.json`（全局）的 `mcpServers` 字段：

```json
{
  "mcpServers": {
    "mastergo-magic-mcp": {
      "command": "npx",
      "args": [
        "-y",
        "@mastergo/magic-mcp",
        "--token=<your_mastergo_token>",
        "--url=https://imd.sankuai.com/"
      ],
      "env": {
        "NPM_CONFIG_REGISTRY": "https://registry.npmjs.org/"
      }
    }
  }
}
```

`--token` 获取方式：登录 imd.sankuai.com → 个人设置 → Access Token。  
`--url` 固定填 `https://imd.sankuai.com/`（美团内网 imd 地址）。  
`NPM_CONFIG_REGISTRY` 指向公网 npm，避免内网 registry 找不到该包。  

> **注意**：Claude Code 通过界面添加的 MCP 实际存储在 `~/.claude/settings.local.json`，该文件由 Claude Code 自动管理，效果等同于手动配置 `settings.json`。

配置完成后重启 Claude Code 使 MCP 生效。若未安装此 MCP，路线 A 会失败，但路线 B（截图）仍可独立运行。

### 路线 B（截图）依赖

- **Chrome**：本机已安装 Google Chrome，并已登录 imd.sankuai.com（SSO 登录态）
- **ws npm 包**：`npm install -g ws`（node 脚本依赖）

---

## 注意事项

- **登录态**：Chrome 独立 profile（`/tmp/chrome-debug-profile`）会复用系统 SSO 登录态，通常无需手动登录
- **Chrome 已在运行**：若用户本机 Chrome 没有带 `--remote-debugging-port` 启动，需用独立 profile 启动新实例（不关闭现有 Chrome）
- **`exportAsync` 权限**：在只读分享模式下完全可用，不受权限限制
- **导出大节点**：整页 Frame 导出可能需要 2-5 秒，B-4 步骤可适当增加等待时间
- **`ws` 模块**：node 脚本依赖 `ws` 包，若报错可先 `npm install -g ws` 或检查本地是否已安装
- **下载文件名**：由 `a.download` 属性决定，使用 `<LAYER_SAFE>_node.png` 格式确保唯一且可预测
- **不要**用快捷键 `⇧⌘C` 复制 PNG，只读模式下无效；`exportAsync` 是正确姿势

---

## 执行要求

### 强制执行

- **必须先完成步骤 0 的链接前置校验**，确认 `fileId`、`pageId`、`layerId` 三个参数均存在且解析成功后，才可进入步骤 1 获取数据
- 必须通过 MCP 或 Chrome CDP 获取真实 DSL/截图数据，不得仅凭链接主观猜测节点结构

### 禁止执行

- **禁止在 `fileId`/`pageId`/`layerId` 任一参数缺失或解析失败的情况下继续执行**，必须立即停止并汇报链接错误
- **禁止将文件级/页面级链接（缺少 `layerId`，仅含 `fileId`+`pageId`）当作单张视觉稿链接处理**，也不得尝试猜测或遍历文件下的具体节点，识别到此类链接必须立即停止并向用户提问澄清
- 禁止在参数缺失时凭空猜测或使用默认值代替
- 禁止直接使用 URL 中的编码值（如 `%3A`）未解码
