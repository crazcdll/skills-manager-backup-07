# 通用前端 CR 规则参考

> 基于酒旅行业规则 [#2815](https://dev.sankuai.com/code/system/rule-set/2815) 、交易前端规则集、交易踩坑记录及社区通用代码规范进行整合，目前分 8 类共 61 条
> 适用文件类型：`*.js, *.jsx, *.ts, *.tsx, *.vue, *.css, *.scss, *.less, *.json, *.yml, *.yaml`
> 更新时间：2026.7.1
>
> **等级说明**：
> - **高**：线上发生时必定造成白屏等严重后果。建议阻塞合并、必须修复。对应 P0
> - **中**：线上发生时有可能影响用户，或导致代码质量严重劣化。建议优化或要求用户说明依据，否则不予放行。对应 P1-P2
> - **低**：对代码质量或长期维护带来一定负面影响。预期优先由 Lint 工具发现，AI 仅在项目无 Lint 配置或 Lint 规则明显缺失时作为兜底报告，不作为主要输出重点。对应 P2-P3

---

## 目录

- [一、命名与文件组织](#一命名与文件组织)
- [二、代码结构与设计](#二代码结构与设计)
- [三、类型安全](#三类型安全)
- [四、异常处理与健壮性](#四异常处理与健壮性)
- [五、安全防护](#五安全防护)
- [六、计算与逻辑正确性](#六计算与逻辑正确性)
- [七、React/Hooks 规范](#七reacthooks-规范)
- [八、前端工程规范](#八前端工程规范)

---

## 一、命名与文件组织

### R01 禁止使用歧视性词语
- **等级**：高
- **描述**：代码和注释禁止使用歧视性、侮辱性、有潜在内容安全或舆情风险的非中性的词语
- **反例**：`beggedVip`、`白嫖用户` 等

### R02 命名清晰明确
- **等级**：中
- **描述**：命名必须清晰表达意图，使用完整单词或公认缩写，避免只有作者能懂的隐晦缩写
- **反例**：`gUI`、`flag`、`data2`、`temp`、`doStuff`（含义不明或无业务语义）

### R03 变量函数命名规范
- **等级**：低，优先 Lint
- **描述**：变量名、函数名使用 lowerCamelCase 风格
- **正例**：`const userName = 'John'`、`function getUserList() {}`
- **反例**：`const user_name = 'John'`、`const UserName = 'John'`

### R04 组件命名规范
- **等级**：低，优先 Lint
- **描述**：组件名使用 PascalCase 风格
- **正例**：`const UserProfile = () => {}`、`export default class OrderList extends Component {}`
- **反例**：`const userProfile = () => {}`、`const user_profile = () => {}`

### R05 常量命名规范
- **等级**：低，优先 Lint
- **描述**：常量使用 UPPER_SNAKE_CASE 风格
- **正例**：`const MAX_RETRY_COUNT = 3`、`const API_BASE_URL = '/api/v1'`
- **反例**：`const maxRetryCount = 3`（用于常量时）、`const api_base_url = '/api/v1'`

### R06 注释简洁明了
- **等级**：高（注释与代码矛盾）/ 中（过度注释）
- **描述**：注释应准确反映代码意图。注释与代码逻辑矛盾（如注释说"返回 true"却返回 false）是高级问题，会导致读者受误；对显而易见的代码过度注释降为中
- **关注点**：
  - 高：注释描述的逻辑与实际代码行为是否一致（AI 可逐行对比验证）
  - 中：注释是否在复述已经清晰的代码逻辑（`// 定义变量 i`、`// 循环遍历`）

### R07 路径命名策略保持一致
- **等级**：中
- **描述**：文件和目录命名应遵循仓库既有约定并保持同层一致；若本次变更新引入 `foo-bar`、`fooBar`、`FooBar` 等互斥风格混用，应指出并请作者说明约定。
- **关注点**：
  - 新建目录或文件是否与兄弟路径同风格
  - 复制、迁移文件后是否引入新的命名体系

### R08 源文件编码与文件名应保持可读、稳定
- **等级**：中
- **描述**：源码文件应使用团队约定的文本编码，通常为 UTF-8；若 diff 中出现乱码、异常换行或明显重复语义的文件命名，应提示其会增加维护成本。
- **关注点**：
  - 是否出现乱码、混合编码、异常换行
  - 父目录已表意时，子文件名是否重复堆叠同义前缀，如 `api/api-log.js`

---

## 二、代码结构与设计

### R09 禁止魔法值
- **等级**：中
- **描述**：表达式中含业务含义的数字字面量和语义不明的字符串，应定义为具名常量统一维护。AI 应重点关注魔法值的**业务语义**（`status === 2` 到底代表什么），而非仅检测字面量存在与否
- **反例**：`if (order.status === 2)` / `if (type === 'HHHH')` — 数字和字符串含义不明

### R10 避免大量内联样式
- **等级**：低，优先 Lint
- **描述**：避免大量的、冗余地使用内联样式，通过 className 选择器编写模块样式
- **反例**：
```jsx
<div style={{color: 'red', fontSize: '14px', margin: '10px 20px', padding: '5px', border: '1px solid #ccc'}}>
```

### R11 避免样式选择器过深嵌套
- **等级**：低，优先 Lint
- **描述**：避免样式选择器过深的嵌套，建议不超过 3 层
- **反例**：
```scss
.page { .container { .content { .list { .item { .title { color: red; } } } } } }
```

### R12 函数长度限制
- **等级**：中，参考 Lint
- **描述**：单个函数业务功能内聚，单个功能函数控制在 100 行内
- **检查方式**：统计函数体行数（不含空行和纯注释行），超过 100 行标记

### R13 函数参数数量限制
- **等级**：中，参考 Lint
- **描述**：函数入参数量不超过 4 个，超过时用对象字面量传参
- **反例**：`function createOrder(userId, productId, quantity, couponId, addressId, remark) {}`

### R14 避免意外的隐式副作用与外部对象修改
- **等级**：高
- **描述**：函数副作用应显式可控；不得直接修改 `props`、入参、外部共享对象，否则会引入不可预测行为和陈旧 UI（浅比较场景下视图不更新）。应通过浅拷贝或不可变方式处理数据。
- **关注点**：纯计算函数中是否意外修改了外部状态；浅比较场景（React state/Redux）是否原地修改。
- **特殊情况**：一般可接受的显示副作用：缓存更新、日志记录、埋点上报、状态管理 dispatch 等
- **反例**：
```js
function calculateTotal(items) {
  globalCache.lastTotal = total; // 隐式副作用
}
props.user.name = newName; // 直接修改 props
items[0].checked = true;   // 原地修改，浅比较下视图不更新
```

### R15 组件复用性设计
- **等级**：中
- **描述**：组件应通过 props/接口灵活扩展，避免耦合特定业务逻辑导致无法复用
- **关注点**：组件内部是否硬编码了接口 URL、业务枚举值/状态码、或直接引用特定页面的 store/context

### R16 组件代码量限制
- **等级**：中，参考 Lint
- **描述**：单个组件代码量不超过 1000 行
- **检查方式**：统计组件文件总行数，超过 1000 行建议拆分

### R17 避免重复代码
- **等级**：高
- **描述**：无明显的代码块重复，遵循 DRY 原则，特别关注跨文件重复
- **关注点**：相似逻辑是否可以抽取为公共函数/组件/Hook

### R18 避免循环依赖
- **等级**：中，参考 Lint
- **描述**：模块间依赖关系清晰，无循环依赖
- **关注点**：A 导入 B，B 又导入 A 的情况

### R19 数据处理高内聚
- **等级**：中
- **描述**：复杂数据结构按业务模块处理，不过度分散
- **关注点**：同一数据的转换/格式化逻辑是否散落在多处

### R20 模块导出方式应易于推理和维护
- **等级**：中
- **描述**：避免不必要的简单转发导出、同路径多行拆分 `import`、可变 `export let`，减少跨文件隐式共享状态和调试成本。
- **例外**：`index.ts` 等聚合入口的聚合导出是 monorepo 标准实践，不属此限
- **反例**：`export { a as default } from './M'`（非聚合入口的简单转发）/ 同路径分两行 import / `export let version = 1`

### R21 自定义事件和多参数接口优先使用对象载荷
- **等级**：中
- **描述**：对自定义事件、发布订阅或多参数回调，优先使用对象承载多个字段，避免位置参数错位、扩展时漏改和调用语义不清。
- **正例**：`emitter.emit('user:update', { id: userId, name: userName })`
- **反例**：`emitter.emit('user:update', userId, userName)`

### R22 非破坏性变更与兼容性
- **等级**：最高
- **描述**：导出的函数、组件、props、参数顺序、默认值等对外契约变更应保持非破坏性；如果存在破坏性变更，需在变更中提供明确迁移方案。
- **关注点**：
  - 参数顺序调整后，旧调用点是否仍然正确
  - 默认值变化后，旧行为是否发生静默变化
  - 导出函数、组件、props 的删改是否影响现有使用方
  - 新增或调整枚举、常量时，是否保留 `unknown/default` 兜底分支
- **反例**：
```js
// 调整了参数顺序，但没有同步修改现有调用点
// function createOrder(quantity: number, userId: string) {}
function createOrder(userId: string, quantity: number) {}
```

---

## 三、类型安全

### R23 使用精确的类型定义
- **等级**：中，参考 Lint
- **描述**：避免滥用 any 和宽泛类型，在非 TypeScript 项目中使用 JSDoc 标注关键类型
- **允许场景**：快速原型开发临时使用、处理动态类型或第三方库、类型过于复杂时的临时方案（但必须添加注释说明原因和后续优化计划）
- **正例**：
```ts
interface UserInfo { id: string; name: string; age: number; }
function getUser(id: string): Promise<UserInfo> {}
```
- **反例**：
```ts
function getUser(id: any): any {}
const data: any = fetchData();
```

### R24 类型导入规范
- **等级**：低，优先 Lint
- **描述**：仅导入类型时使用 `import type { } from xxx`
- **正例**：`import type { UserInfo } from './types'`
- **反例**：`import { UserInfo } from './types'`（当 UserInfo 仅作为类型使用时）

### R25 超大整数使用字符串类型
- **等级**：高
- **描述**：超大整数场景（如门店ID、商品ID），前端接收时使用 String 字符串类型
- **正例**：`const shopId: string = response.shopId`
- **反例**：`const shopId: number = response.shopId`（当 ID 超过 Number.MAX_SAFE_INTEGER 时会丢失精度）

---

## 四、异常处理与健壮性

### R26 JSON.parse 异常捕获
- **等级**：高
- **描述**：JSON.parse 使用 try-catch 进行异常捕获
- **正例**：
```js
let data;
try { data = JSON.parse(rawStr); } catch (e) { data = defaultValue; }
```
- **反例**：
```js
const data = JSON.parse(rawStr); // 若 rawStr 非法 JSON 将直接抛异常
```

### R27 异常不用作流程控制
- **等级**：高
- **描述**：异常机制用于处理意外错误，不应用于控制正常业务流程；用 try-catch 处理可预期的条件分支会掩盖真正的异常、降低可读性并影响性能
- **关注点**：是否用 try-catch 来判断某个值是否存在、某个操作是否成功等本可用 if 处理的逻辑
- **反例**：
```js
// 用异常判断数据类型，应改用 typeof/instanceof
try { processAsArray(data); } catch (e) { processAsObject(data); }
// 用异常判断属性是否存在，应改用 in 或可选链
try { return obj.user.name; } catch (e) { return ''; }
```

### R28 异步流程必须完整处理状态与时序
- **等级**：高
- **描述**：异步代码需处理所有分支，避免永远 pending 的 Promise、遗漏 `await`、未处理 rejection、以及因时序错误引发的竞态问题
- **关注点**：
  - `new Promise` 中所有条件分支是否都调用了 `resolve`/`reject`
  - `async` 函数是否遗漏 `await`（导致 `try/catch` 失效）
  - 串行流程是否误写成并行，或并行结果存在时序覆盖
- **反例**：
```ts
new Promise((resolve) => {
  if (condition) resolve(data); // else 分支缺失，永远 pending
});
try {
  fetchDetail(); // 遗漏 await，catch 永远不会触发
} catch (e) { reportError(e); }
```

### R29 合理进行空值保护
- **等级**：最高
- **描述**：对可能为 null/undefined 的数据（接口返回、路由参数、深层对象链、可选回调）必须保护；对类型确定非空的数据不做冗余保护。外部输入是历史高频线上问题，重点关注。
- **关注点**：`any`/`unknown`/未完成类型收窄的数据不能直接访问属性
- **反例**：`response.data.cityInfo.name`（无保护）/ `requiredUser?.name ?? ''`（冗余保护，噪音）

### R30 类型转换必须明确区分有效值和无效值
- **等级**：高
- **描述**：类型转换必须明确区分有效值和无效值，避免错误覆盖有效数据（如数字 `0`、空字符串 `''`），根据业务场景选择合适的转换策略
- **关注点**：
  - `value || default` — `0`/`''`/`false` 会被错误覆盖，应改用 `?? ` 或显式 null 判断
  - `!!value` 作为布尔转换 — `0`/`''` 会被当作 false，需确认业务上 0 是否为有效值
  - `Boolean(value)` 同上，在数字/字符串场景需谨慎
- **反例**：`const count = value || 0` — value 为 `0` 时被错误覆盖为默认值

### R31 并发请求与重复提交控制
- **等级**：高
- **描述**：提交按钮、刷新、高频监听等场景应有去重/防抖/节流/幂等保护，避免重复提交和时序覆盖（并行请求后返回覆盖先返回）
- **关注点**：`scroll`/`resize`/`input` 等高频事件直接触发渲染或请求时，必须有节流/防抖，否则会严重影响页面性能
- **反例**：`button.onClick = async () => { await submitOrder(); }` — 无任何防止重复保护

### R32 请求结果需完整处理错误与空数据
- **等级**：高
- **描述**：请求不能只处理成功分支，需覆盖：网络错误、业务错误（包括但不限于code 非 0，根据项目实际情况灵活判断）、空数据兜底、loading 状态维护、组件卸载后的更新防护
- **反例**：`request(params).then(res => setList(res.data.list))` — 无错误处理、无 loading、无空数据兜底

---

## 五、安全防护

### R33 生产环境禁止输出敏感信息
- **等级**：高
- **描述**：生产环境禁止使用 console.log 输出敏感信息
- **反例**：`console.log('user token:', token)`、`console.log('password:', pwd)`

### R34 生产环境禁止输出 debug 日志
- **等级**：低，优先 Lint
- **描述**：谨慎地记录日志，生产环境禁止输出 debug 日志
- **关注点**：是否有大量 console.log/debug 语句未清理

### R35 XSS 防护
- **等级**：高
- **描述**：将用户可控内容（表单输入、URL 参数、接口返回的富文本）直接注入 DOM 是高危操作，必须经过转义或使用安全渲染方式
- **关注点**：
  - `dangerouslySetInnerHTML`/`v-html`/`innerHTML` 渲染的内容来源是否为用户可控
  - `location.search`、`URLSearchParams`、路由参数等 URL 来源的内容是否直接注入 DOM
  - 富文本编辑器保存的内容渲染时是否使用了白名单过滤（如 DOMPurify）
  - 纯静态字符串常量可不处理；仅当内容来源不可信时才需要转义

### R36 禁止硬编码认证凭据

> 除脚本外，亦需检查 `*.json`、`*.md`、`*.yml`、`*.yaml` 等配置与 `*.md` 等文档中的硬编码。

- **等级**：高
- **描述**：禁止源码中硬编码认证凭据类信息，如私钥、token、认证密码、API 密钥等
- **反例**：
```js
const API_KEY = 'sk-<api-key>';
const DB_PASSWORD = 'plain-text-password';
```

### R37 避免动态执行代码
- **等级**：高
- **描述**：避免使用 eval()、Function() 等动态执行代码的方法
- **反例**：
```js
eval(userInput);
new Function('return ' + expr)();
```

### R38 敏感信息脱敏
- **等级**：高
- **描述**：个人敏感信息必须脱敏，展示和日志打印均需处理；日志打印是高频漏点，因为开发阶段容易遗留
- **关注点**：
  - 页面展示：手机号、身份证号、银行卡号等是否做了掩码（如 `138****8888`）
  - 日志打印：`console.log(userInfo)` / `reportLog({ phone })` 是否将完整敏感字段输出
  - 错误上报：catch 块中上报的 error 对象是否包含了用户隐私数据

### R39 严格限定 CORS 策略

> 检查重点为 `*.js`、`*.ts` 中的 CORS / 跨域响应头与代理配置。

- **等级**：高
- **描述**：禁止未限制的跨域请求，严格限定 CORS 策略
- **关注点**：前端常见场景是 devServer proxy 配置中的宽泛 `changeOrigin`/`target` 泄露到生产构建，或 BFF/Node 层响应头设置了 `Access-Control-Allow-Origin: *`
- **反例**：`Access-Control-Allow-Origin: *`

### R40 Cookie 禁止存储敏感信息
- **等级**：高
- **描述**：禁止在 Cookie 中存储敏感信息如用户密码、加解密密钥等

### R41 禁止通过 GET 参数传递长期认证 Token
- **等级**：高
- **描述**：禁止通过 GET 参数传递长期认证类的 Token，推荐在请求头或者 Cookie 中进行传输
- **反例**：
```js
fetch(`/api/data?token=${authToken}`);
```

### R42 文件上传类型限制
- **等级**：高
- **描述**：文件上传功能，仅允许业务所需文件类型上传
- **关注点**：是否对 accept 属性和文件类型做了校验

### R43 禁止硬编码业务数据或 Mock 数据
- **等级**：高
- **描述**：禁止业务数据/Mock 数据带入生产；`MOCK_`/`TEST_`/`DEBUG_` 前缀常量、mock 开关、`debugger` 语句应在上线前清理
- **反例**：`const MOCK_USERS = [...]`、`const users = useMock ? MOCK_USERS : await fetchUsers()`、`debugger`

---

## 六、计算与逻辑正确性

### R44 递归调用规范
- **等级**：高
- **描述**：递归调用重点检查是否存在无限循环的风险
- **关注点**：是否有明确的终止条件、递归深度是否可控

### R45 条件判断必须逻辑正确且有意义
- **等级**：高
- **描述**：条件判断必须逻辑正确且有意义，避免出现永远为真/假的条件、无效比较和逻辑矛盾
- **正例**：
```js
if (status === 'active' && count > 0) { ... }
```
- **反例**：
```js
if (true) { ... }
if (x !== x) { ... } // 除 NaN 外永远为 false
if (a > 10 && a < 5) { ... } // 逻辑矛盾
```

### R46 浮点数精度比较规范
- **等级**：高
- **描述**：避免直接使用 === 比较浮点数运算结果
- **正例**：
```js
Math.abs(0.1 + 0.2 - 0.3) < Number.EPSILON
```
- **反例**：
```js
0.1 + 0.2 === 0.3 // false!
```

### R47 NaN 比较错误
- **等级**：高
- **描述**：必须使用 isNaN() 或 Number.isNaN() 检查 NaN，不能使用 === NaN
- **正例**：`if (Number.isNaN(value)) { ... }`
- **反例**：`if (value === NaN) { ... }` // 永远为 false

### R48 循环边界检查规范
- **等级**：高
- **描述**：循环条件必须确保索引在有效范围内，避免越界访问
- **正例**：
```js
for (let i = 0; i < arr.length; i++) { console.log(arr[i]); }
```
- **反例**：
```js
for (let i = 0; i <= arr.length; i++) { console.log(arr[i]); } // 最后一次越界
```

### R49 数值解析和有限数判断必须显式
- **等级**：高
- **描述**：`parseInt` 必须显式传入 `radix`；用 `Number.isFinite` 而非全局 `isFinite`（后者有隐式类型转换）
- **反例**：`parseInt(rawPage)` / `isFinite(rawAmount)`

### R50 数组高阶方法的回调返回语义必须完整
- **等级**：中
- **描述**：`map`/`filter`/`reduce`/`sort` 等高阶方法的回调各分支需有明确 `return`；`sort` 比较函数应返回负/零/正数
- **反例**：`list.map(item => { if (item.skip) return null; transform(item); })` — 最后一行漏 return

---

## 七、React/Hooks 规范

> 下列以 React Hooks / JSX 为主表述；如涉及 Vue 等栈请按组合式 API、生命周期钩子的等价语义对照。

### R51 状态更新依赖错误
- **等级**：高
- **描述**：在**异步回调、定时器、连续多次调用、或依赖前一次更新结果**的场景中，直接引用 state 变量会捕获到旧值，必须改用函数式更新。同步事件处理器中单次调用不在此限。
- **关注点**：`setTimeout`/`setInterval`/Promise 回调中的 setState；同一事件处理器中连续多次 setState 依赖同一 state
- **反例**：
```jsx
// ❌ 连续调用只 +1 而非 +2，两次都拿到旧值
const handleDoubleIncrement = () => {
  setCount(count + 1);
  setCount(count + 1);
};
// ❌ 异步回调中使用过期闭包
setTimeout(() => setCount(count + 1), 1000);
```
- **正例**：`setCount(prev => prev + 1)` — 函数式更新始终基于最新值

### R52 useEffect 不合理的空依赖数组
- **等级**：高
- **描述**：`useEffect` 使用 `[]` 空依赖数组时，回调内引用的外部变量会被静默捕获为初始值，后续变量变化不会触发重新执行，产生隐蔽的过期数据问题。
- **关注点**：空依赖数组内是否引用了可能随时间变化的 props、state 或外部变量
- **正例**：
```jsx
useEffect(() => { fetchUser(userId); }, [userId]); // userId 变化时重新执行
```
- **反例**：
```jsx
useEffect(() => {
  fetchUser(userId); // userId 变化后此处仍使用初始值
}, []); // 空数组：只在挂载时执行一次，userId 更新被静默忽略
```

### R53 引用比较误用
- **等级**：高
- **描述**：依赖数组中不能放每次渲染都会新创建的对象/函数，会导致无限重渲染；应用 `useMemo`/`useCallback` 稳定引用
- **反例**：`useEffect(() => { init({ theme: 'dark' }); }, [{ theme: 'dark' }])` — 对象每次渲染都是新引用

### R54 React 组件声明、默认值和 ref 用法
- **等级**：中；字符串 `ref` 为高
- **描述**：组件声明优先具名；可选 props 使用前需有默认值；禁止使用字符串 `ref`
- **关注点**：可选 props 未给默认值时是否可能直接触发运行时错误（如 `suffix.toUpperCase()`）
- **反例**：`({ title, suffix }) => <div>{title}{suffix.toUpperCase()}</div>` — suffix 为 undefined 时崩溃；`ref="field"` — 字符串 ref 已废弃

### R55 不要无差别透传 props
- **等级**：中
- **描述**：组件向子级或 DOM 透传参数时，至少应解构剥离已知不应下传的字段（事件处理器、业务 props），剩余部分透传是可接受的；禁止将全量 props 直接传给 DOM 元素
- **反例**：`return <div {...this.props} />` — 业务 props 会污染 DOM 属性
- **可接受**：`const { onExtraClick, ...rest } = props; return <Child {...rest} />` — 已剥离不应下传的字段

### R56 禁止在条件或循环中改变 Hook 调用顺序
- **等级**：高
- **描述**：Hook 必须保持稳定调用顺序，不能在条件、循环或提前 return 等路径中少调、多调，否则将触发运行时报错并破坏状态对应关系。
- **正例**：
```jsx
useEffect(() => {
  if (visible) {
    trackExpose();
  }
}, [visible]);
```
- **反例**：
```jsx
if (visible) {
  useEffect(() => {
    trackExpose();
  }, []);
}
```

### R57 条件渲染的边界语义
- **等级**：中
- **描述**：`0`、`NaN`、`''` 等 falsy 值在 JSX 渲染上下文与布尔判断中行为不同，容易导致非预期内容渲染或隐藏，且语法合法不报错，AI 审查时需主动识别
- **关注点**：
  - `{count && <Comp />}` — count 为 `0` 时渲染出字符 `0`，应改为 `{count > 0 && <Comp />}`
  - `{text ? <A /> : <B />}` — text 为 `0`/`''`/`NaN` 时走 `<B />` 分支，需确认是否符合业务预期
  - `arr.filter(Boolean)` — 会过滤掉数组中有效的 `0`/`''` 元素，若业务上这些是合法值应改用显式条件
  - NaN 在模板中会渲染为文本 `NaN`，来源通常是 `Number(undefined)`、未初始化的计算结果等

### R58 副作用资源必须清理
- **等级**：高
- **描述**：在副作用中创建的订阅、事件监听、定时器、轮询、原生监听器等资源必须在 cleanup 中释放，避免内存泄漏和重复触发。
- **关注点**：
  - `useEffect` 中注册的事件、订阅、timer 是否有对应清理
  - 页面切换、组件卸载后是否仍然保留活跃监听
  - 原生桥接、全局事件、滚动监听等场景是否遗漏 cleanup
- **正例**：
```tsx
useEffect(() => {
  const timer = setInterval(fetchData, 1000);
  const unsubscribe = eventBus.subscribe('refresh', handleRefresh);
  return () => {
    clearInterval(timer);
    unsubscribe();
  };
}, []);
```
- **反例**：
```tsx
useEffect(() => {
  window.addEventListener('resize', handleResize);
  // 缺少 cleanup
}, []);
```

### R59 卸载后异步更新防护
- **等级**：高
- **描述**：异步请求、Promise 回调、原生回调完成时组件可能已经卸载，应避免在卸载后继续执行状态更新、副作用或 UI 操作。
- **关注点**：
  - 请求返回后是否直接调用 `setState`、`setData`、导航、弹窗等操作
  - 是否使用 mounted flag、AbortController、请求取消机制或等价守卫
  - 多次请求并发时，旧请求是否可能覆盖新请求结果
- **正例**：
```tsx
useEffect(() => {
  let mounted = true;
  fetchData().then(data => {
    if (!mounted) return;
    setData(data);
  });
  return () => { mounted = false; };
}, []);
```
- **反例**：
```tsx
useEffect(() => {
  fetchData().then(setData); // 卸载后仍触发 setState
}, []);
```

---

## 八、前端工程规范

### R60 版本号 version spec 必须合规
- **等级**：中
- **描述**：依赖版本号必须是合法的 semver range，禁止 `latest`、`*`、空字符串等不可控 spec，以及未经团队约定的 `git+ssh://`、本地路径协议（monorepo 内 `workspace:*` 等既定协议除外）
- **反例**：`"lodash": "latest"`、`"axios": " 1.0.0"`、`"some-pkg": ""`

### R61 依赖声明禁止重复
- **等级**：中
- **描述**：同一包名不得同时出现在 `dependencies` 和 `devDependencies`（或 `peerDependencies`）中；同一 monorepo 内多个子包对同一依赖声明不同版本，若无明确理由（如故意锁定旧版本），应指出并建议收敛
- **反例**：`dependencies` 声明 `"react": "^18.2.0"`，`devDependencies` 又声明 `"react": "^17.0.2"`

