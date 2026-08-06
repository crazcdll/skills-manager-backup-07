# 注意事项

1. **依赖完整性**：struct/logics 中用到的所有 proCode 组件/逻辑库，都必须在 dependencies 和 componentsMap 中声明
2. **URL 路径区分**：logic 类型使用 `/logic/` 路径，component 类型使用 `/material/` 路径
3. **lowCode 组件**：不需要在 dependencies 中声明，也没有 `web` URL
4. **数据表达式是 Groovy**：`data` 字段是后端 Groovy 表达式，使用 `?:` Elvis 运算符和 `.size()` 方法
5. **字符串字面量**：写法是 `"data": "'字符串值'"` （外双内单）
6. **styles 结构**：使用 `"style"` key + Object sub 结构，而非直接写属性名
7. **buildConfig 字段**：所有 resource 都需要包含 `"buildConfig": null`
8. **constData 限制**：常量只能在 struct 中使用，**不能**在 reqProps（入参）中使用
9. **logics 标配**：大多数页面需要 `common-duo-lifecycle` + `common-event-nav`，在 lifecycle 的 `preview.onResponse` 中设置标题
10. **materialId 和 id 获取方式**：`componentsMap` 的 key是物料的ID（materialId），优先通过 `duo yooz-*` CLI 查询；若 CLI 失败则降级使用 MCP 工具；若均查询不到，从现有协议 JSON 文件`references/materials.json`中复制同一物料的配置。**绝对不能自行编造**，最后对**materialId**进行二次检查
11. **拆分成的groovy 文件**必须是合法的groovy语法，groovy 的版本 2.4.17，一些较新的语法不支持，请严格参考以下 **Groovy 语法禁用清单** 进行二次确认，禁止非法语法。

> **🔴 核心铁律**：所有 .groovy 文件绝对禁止添加任何形式的注释。无例外、无条件、无豁免。
> - ❌ `.groovy` 文件 → **禁止任何注释**（包括 `//`、`/* */`、行尾注释、文件头注释）
> - 违反后果：平台解析直接报错 `Unexpected char "/"`，协议无法加载。

**Groovy 语法禁用清单（Good vs Bad）**：

| # | MUST_NOT（禁止写法） | MUST（正确写法） | 平台报错信息 |
| -- | --------------------- | ----------------- | ------------- |
| 1 | 使用 `//` 或 `/* */` 注释 | 完全移除所有注释 | `Unexpected char "/"` |
| 2 | `styles { object('style') }` | `style('styleName')` | `Unexpected token "}"` |
| 3 | `advanced { bool('displayRule') }` | `xIf {{ expr }}` | `Unexpected token "}"` |
| 4 | `events { emit { ... } }` JSON 数组 | `on('eventName') { callMethod() }` | `Unexpected token "["` |
| 5 | `constData.groovy` 中使用 `constData` 关键字 | 使用 `constant` 关键字 | `Unknown identifier` |
| 6 | `submitBizRespStatus` 中使用 `errorNoReturnStruct` | 该关键字只在 `bizRespStatus` 中有效 | `Unknown identifier` |
| 7 | 样式中 `string('flex') {{ '1' }}` | `number('flex') {{ 1 }}` | 样式值类型不匹配 |
| 8 | 颜色值不写引号 `{{ #FFFFFF }}` | `string('backgroundColor') {{ '#FFFFFF' }}` | 颜色值缺引号导致解析失败 |
| 9 | CSS 简写 `{{ '10px 20px' }}` | 拆分为 marginTop/marginBottom 等单独属性 | DUO 基于 RN 不支持 CSS 简写 |
| 10 | RN 不支持的样式 `display`/`float`/`position:absolute` | 使用 flex 布局替代 | RN 不支持该 CSS 属性 |
| 11 | 使用 `===`（严格等于） | Groovy 2.4.17 用 `==` | — |
| 12 | 使用 `var` 声明变量 | Groovy 2.4.17 用 `def` | — |
| 13 | 使用箭头函数`=>`、模板字符串`` ` `` 、解构赋值等现代 JS 语法 | 使用 Groovy 原生语法 | — |

**字符串字面量规则**：外双内单格式 `"data": "'字符串值'"`；空值兜底统一使用 `?:` Elvis 运算符；每级属性访问都必须加 `?.` 安全操作符。
