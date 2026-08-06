# insert_html / edit_html 使用规范

`insert_html` / `edit_html` 用于把可信、自生成或用户明确认可的 HTML fragment 写入学城编辑器原生 `html` 宏节点。它适合文档原生节点表达不了的交互、动画和动态生成视图，不适合普通正文、普通表格、普通图片或可编辑图表。

## 适用场景

优先使用 HTML 宏的场景：

- 交互演示：流程模拟、状态机演示、算法可视化、产品动效 Demo、可点击架构说明。
- 动态视图：根据内置 JSON/CSV 数据渲染指标卡、轻量 dashboard、趋势图、分布图、筛选视图。
- 互动阅读：slides、timeline、decision matrix、runbook/checklist、quiz、翻卡片、折叠式报告摘要。
- 强视觉内容块：报告封面、管理层摘要、专题卡片墙、对比面板，但必须仍然服务文档阅读，不做纯装饰。
- 用户提供了现成 HTML/CSS/JS，且目标就是以学城 HTML 宏渲染，而不是转换成可编辑正文。

不应使用 HTML 宏的场景：

- 普通段落、标题、列表、表格等可编辑正文结构：使用 `paste` 或官方 `citadel`。
- Mermaid / PlantUML / DrawIO / Minder / Yuntu / Data2Chart 等已有原生节点能力：先使用对应专门 skill 或结构化 op，不要退化成通用 HTML 宏。
- 普通图片、附件、视频、音频：优先官方上传/插入链路。
- 需要长期维护为文档正文、需要多人直接编辑局部内容的文本块。
- 需要访问后端、读取登录态、提交表单、上报数据或持久保存用户交互状态的应用。

## 内容边界

HTML 宏应定位为“文档内嵌轻应用”或“自包含展示块”：

- 数据默认内联在源码里，例如 JSON 数组、静态 CSV 文本、手写配置对象。
- 交互状态只存在于当前页面运行时，刷新后可以重置；不要承诺持久化。
- 不依赖外部构建产物、npm、CDN JS、远程 API 或 localhost。
- 如果内容需要真实实时数据，优先 Yuntu/Data2Chart；HTML 宏只适合小型定制展示或快照。
- 如果内容需要可编辑图形，优先 DrawIO/Mermaid/PlantUML/Minder；HTML 宏只适合交互说明，不替代图表源编辑。

## HTML Fragment 格式

传给 `html.content` 的内容必须是 HTML fragment，不是完整页面：

```html
<style>
  /* all CSS here */
</style>
<div class="km-custom-block" data-km-custom-block="1">
  ...
</div>
<script>
  /* top-level script here */
</script>
```

必须遵守：

- 不包含 `<!doctype>`、`<html>`、`<head>`、`<body>`。
- CSS、HTML、JS 全部自包含。
- `<script>` 必须是顶层兄弟节点，不要嵌在 root div 内部；学城 HTML 宏只稳定执行顶层 script。
- 使用唯一 root class / data attribute，避免污染同页其他 HTML 宏或学城页面。
- 所有 CSS 选择器都挂在唯一 root class 下，不写全局 `body`、`button`、`table`、`:root` 等页面级样式。
- 不使用 `document.body.innerHTML = ...` 或全局清空 DOM 的写法。
- 绑定脚本时使用 `:not([data-bound])` 或类似标记避免重复绑定。

推荐脚本绑定模式：

```html
<script>
(() => {
  document.querySelectorAll(".km-custom-block[data-km-custom-block='1']:not([data-bound])").forEach((root) => {
    root.dataset.bound = "1";
    // bind events and render dynamic content here
  });
})();
</script>
```

## 布局规范

- 宏容器宽度使用 `width: 100%; max-width: 100%; box-sizing: border-box;`。
- 学城编辑器 `html` 节点没有稳定的 `width` / `height` attrs；不要在 `insert_html` / `edit_html` payload 里传宽高。
- 固定比例内容使用 CSS `aspect-ratio`，不要默认使用 `72vh` 这类视口高度。
- 非固定比例内容使用自然高度，但要控制最大密度，避免生成一个超长、难以阅读的宏。
- 卡片圆角不超过 `8px`，除非是 pill/tab 这类控件。
- 文本必须在桌面和窄屏下都能放入容器；必要时改为单列布局。
- 使用稳定尺寸约束，例如 `minmax()`、`aspect-ratio`、`min-height`、`max-width`，避免 hover 或数据变化造成布局跳动。
- 内容过多时拆成多个区域或多页，不要把所有信息压缩到一个密集面板里。

响应式基本结构：

```css
.km-custom-block,
.km-custom-block * {
  box-sizing: border-box;
}

.km-custom-block {
  width: 100%;
  max-width: 100%;
  overflow: hidden;
}

@media (max-width: 760px) {
  .km-custom-block .grid {
    grid-template-columns: 1fr;
  }
}
```

## 交互规范

- 交互控件必须有明确点击目标，例如 button、tab、segmented control、toggle、slider。
- 不要只依赖键盘事件；iframe 未聚焦时键盘可能不可用。
- 点击、触摸或鼠标操作应足以完成主要交互。
- 动态渲染内容使用 DOM API 或受控的模板字符串；输入来自用户时必须先转义，不要直接拼接成 HTML。
- 不要拦截学城页面级快捷键，不要绑定全局 `window` 键盘事件，除非交互块获得焦点后才处理。
- 不要创建覆盖整个页面的 fixed 遮罩；所有交互应限制在宏容器内部。
- 需要复制命令、展开详情、切换数据时，状态变化要有可见反馈。

## 动画规范

- 动画用于解释状态变化、引导视线或增强展示，不要做持续干扰阅读的装饰动画。
- 使用 CSS transition/animation 或轻量 JS 更新 class；避免长时间 `setInterval`、大量 canvas 粒子或持续高频重绘。
- 必须支持 `prefers-reduced-motion`。
- 动画时长保持克制：常规切换 120-420ms，复杂过渡不超过 700ms。
- 不使用无限循环闪烁、快速缩放、强烈视差或大面积背景动效。

基本降级：

```css
@media (prefers-reduced-motion: reduce) {
  .km-custom-block * {
    animation-duration: 1ms !important;
    transition-duration: 1ms !important;
    scroll-behavior: auto !important;
  }
}
```

## 资源与图片

- 本地图片必须先通过官方学城/Citadel 上传到目标文档，再在 HTML 中引用 KM 托管 URL。
- HTML 宏中不能引用 `file://`、本地绝对路径、临时相对路径、localhost 资源。
- 默认不要把图片转成 base64；base64 会让宏源码过大且难以排查。
- 外部远程图片只有用户明确要求保留外链时才直接引用；否则下载并上传到 KM。
- 图片必须有 `alt`，并设置 `max-width`、`max-height`、`object-fit`。
- 装饰性 SVG 可以内联，但可编辑 DrawIO/Mermaid/Minder 产物不要降级成 HTML 内普通图片。

## 安全约束

- 只插入可信、自生成或用户明确认可的 HTML。
- 学城编辑器不会替你对 HTML 宏源码做业务级 sanitizer；不要插入来源不明的脚本。
- 不读取、展示或传输 cookie、localStorage、token、页面中的敏感信息。
- 不向第三方 URL 发送请求，不提交表单，不创建账号，不进行任何代表用户的外部操作。
- 不加载远程 JS，不使用 `eval`、`new Function`、动态 script 注入。
- 不使用 `postMessage` 和父页面通信，除非已有明确、受控、文档化的协议。
- 不把用户敏感数据写进 HTML 宏源码，除非用户明确要求并确认目标文档可见范围。

## 可维护性

- root class 应包含语义和唯一后缀，例如 `.km-dashboard-<docId>` 或 `.km-arch-cards-<docId>`。
- `html.source` 使用稳定标识，例如 `km-dashboard`、`km-architecture-cards`、`km-interactive-demo`。
- 内容复杂时先保存 HTML fragment 到 `/tmp/km-<type>-<docId>.html`，检查后再包装成 ops。
- 源码里可以有少量注释解释复杂数据映射，但不要堆大量生成器说明。
- 如果同一文档连续插入多个 HTML 宏，同一锚点 `insert + after` 的视觉顺序可能反转；必要时反向提交 ops 或使用不同锚点。

## 质量检查

插入前至少检查：

- 没有 `file://`、`localhost`、`127.0.0.1`、未上传图片、外部 JS/CDN。
- 没有 `<!doctype>`、`<html>`、`<head>`、`<body>`。
- `<script>` 是顶层兄弟节点。
- root class / data attribute 唯一。
- 桌面宽度下首屏不空白、不溢出；窄屏下布局可读。
- 主要交互通过鼠标点击可用。
- 动画有 `prefers-reduced-motion` 降级。

插入后至少验证：

- `kmedit browser-apply` 返回 `ok: true` 且 save 成功。
- `kmedit browser-inspect --force-refresh` 能看到目标 `html` 节点。
- 浏览器中能看到非空渲染内容。
- 如果有交互，点击至少一个主要控件确认 JS 已执行。

## Ops 示例

插入：

```json
{
  "operations": [
    {
      "op": "insert_html",
      "position": "after",
      "target": { "nodeId": "anchor_node" },
      "html": {
        "source": "km-interactive-demo",
        "content": "<style>...</style><div class=\"km-interactive-demo\" data-km-interactive-demo=\"1\">...</div><script>...</script>"
      }
    }
  ]
}
```

更新：

```json
{
  "operations": [
    {
      "op": "edit_html",
      "target": { "nodeId": "html_node" },
      "html": {
        "content": "<style>...</style><div class=\"km-interactive-demo\" data-km-interactive-demo=\"1\">...</div><script>...</script>"
      }
    }
  ]
}
```
