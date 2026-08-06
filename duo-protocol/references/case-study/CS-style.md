# 组件样式编写规范

本文档总结了 DUO 协议中组件样式的编写规则、常用属性、正确示例与错误案例。

## 目录

- [一、样式语法规则](#一样式语法规则) — Groovy DSL 语法、JSON 协议语法
- [二、常用样式属性](#二常用样式属性) — 布局/尺寸/间距/视觉相关属性速查表
- [三、Good Case（正确示例）](#三good-case正确示例) — 卡片容器、Flex 两端布局、居中布局、行内布局
- [四、Bad Case（错误示例）](#四bad-case错误示例) — styles 语法错误、类型不匹配、颜色值缺引号、表达式格式错误
- [五、禁止 Case（严禁使用）](#五禁止-case严禁使用) — 禁止注释、JS/CSS 风格、RN 不支持的样式、动态计算
- [六、样式属性类型速查表](#六样式属性类型速查表) — 尺寸/颜色/枚举/布尔值类型对照
- [七、常见问题排查](#七常见问题排查) — 样式不生效、解析报错、布局异常

---

## 一、样式语法规则

### 1.1 Groovy DSL 样式语法

在 `struct.groovy` 中，使用 `style('styleName')` 块定义样式：

```groovy
node('ComponentName', 'materialId') {
  style('style') {
    string('backgroundColor') {{ '#FFFFFF' }}
    number('marginBottom') {{ 10 }}
    number('flex') {{ 1 }}
  }
}
```

**语法要点**：
- 使用 `style('styleName')` 而非 `styles { object('style') ... }`
- 样式属性值使用类型声明：`string()` / `number()` / `bool()`
- 表达式使用双大括号 `{{ }}` 包裹

### 1.2 JSON 协议样式语法

在完整 JSON 协议中，样式通过 `styles` 字段定义：

```json
"styles": {
  "style": {
    "dataType": "Object",
    "__resolveType__": "BACK_END",
    "sub": {
      "marginBottom": {
        "dataType": "Number",
        "__resolveType__": "BACK_END",
        "data": "10"
      },
      "backgroundColor": {
        "dataType": "String",
        "__resolveType__": "BACK_END",
        "data": "'#FFFFFF'"
      }
    }
  }
}
```

---

## 二、常用样式属性

### 2.1 布局相关

| 属性名　　　　　 | 类型　 | 说明　　　　 | 示例　　　　　　　　　　　　　　　　　　　　　　 |
| ------------------| --------| --------------| --------------------------------------------------|
| `flex`　　　　　 | Number | 弹性布局比例 | `number('flex') {{ 1 }}`　　　　　　　　　　　　 |
| `flexDirection`　| String | 主轴方向　　 | `string('flexDirection') {{ 'row' }}`　　　　　　|
| `justifyContent` | String | 主轴对齐　　 | `string('justifyContent') {{ 'space-between' }}` |
| `alignItems`　　 | String | 交叉轴对齐　 | `string('alignItems') {{ 'center' }}`　　　　　　|
| `flexWrap`　　　 | String | 换行方式　　 | `string('flexWrap') {{ 'wrap' }}`　　　　　　　　|

### 2.2 尺寸相关

| 属性名 | 类型 | 说明 | 示例 |
|--------|------|------|------|
| `width` | Number | 宽度 | `number('width') {{ 200 }}` |
| `height` | Number | 高度 | `number('height') {{ 50 }}` |
| `minWidth` | Number | 最小宽度 | `number('minWidth') {{ 100 }}` |
| `maxWidth` | Number | 最大宽度 | `number('maxWidth') {{ 300 }}` |

### 2.3 间距相关

| 属性名 | 类型 | 说明 | 示例 |
|--------|------|------|------|
| `margin` | Number | 四边外边距 | `number('margin') {{ 10 }}` |
| `marginTop` | Number | 上外边距 | `number('marginTop') {{ 10 }}` |
| `marginBottom` | Number | 下外边距 | `number('marginBottom') {{ 10 }}` |
| `marginLeft` | Number | 左外边距 | `number('marginLeft') {{ 12 }}` |
| `marginRight` | Number | 右外边距 | `number('marginRight') {{ 12 }}` |
| `padding` | Number | 四边内边距 | `number('padding') {{ 16 }}` |
| `paddingTop` | Number | 上内边距 | `number('paddingTop') {{ 12 }}` |
| `paddingBottom` | Number | 下内边距 | `number('paddingBottom') {{ 12 }}` |
| `paddingLeft` | Number | 左内边距 | `number('paddingLeft') {{ 16 }}` |
| `paddingRight` | Number | 右内边距 | `number('paddingRight') {{ 16 }}` |

### 2.4 视觉相关

| 属性名 | 类型 | 说明 | 示例 |
|--------|------|------|------|
| `backgroundColor` | String | 背景色 | `string('backgroundColor') {{ '#FFFFFF' }}` |
| `borderRadius` | Number | 圆角 | `number('borderRadius') {{ 8 }}` |
| `borderWidth` | Number | 边框宽度 | `number('borderWidth') {{ 1 }}` |
| `borderColor` | String | 边框颜色 | `string('borderColor') {{ '#E5E5E5' }}` |
| `opacity` | Number | 透明度 | `number('opacity') {{ 0.5 }}` |
| `overflow` | String | 溢出处理 | `string('overflow') {{ 'hidden' }}` |

---

## 三、Good Case（正确示例）

### 3.1 卡片容器样式

```groovy
node('DealInfoCard', '37') {
  label '商品信息卡片'
  props {
    string('lineMode') {{ 'multiple' }}
  }
  style('style') {
    number('marginLeft') {{ 12 }}
    number('marginRight') {{ 12 }}
    number('marginTop') {{ 10 }}
    number('marginBottom') {{ 10 }}
    string('backgroundColor') {{ '#FFFFFF' }}
    number('borderRadius') {{ 8 }}
  }
}
```

### 3.2 Flex 两端布局

```groovy
node('BottomSubmitBar', '37') {
  label '底部提交栏'
  props {
    string('lineMode') {{ 'single' }}
  }
  style('style') {
    number('paddingLeft') {{ 16 }}
    number('paddingRight') {{ 16 }}
    string('backgroundColor') {{ '#FFFFFF' }}
  }
  slot('children') {
    node('TotalPriceText', '38') {
      label '总金额'
      props {
        string('type') {{ 'title2' }}
        string('color') {{ '#FF6600' }}
        string('text') {{ '¥128' }}
      }
      style('style') {
        number('flex') {{ 1 }}
      }
    }
    node('SubmitButton', '36') {
      label '提交按钮'
      props {
        string('type') {{ 'primary' }}
        string('text') {{ '提交订单' }}
      }
    }
  }
}
```

### 3.3 居中布局

```groovy
node('CenterContainer', '37') {
  label '居中容器'
  style('style') {
    number('flex') {{ 1 }}
    string('justifyContent') {{ 'center' }}
    string('alignItems') {{ 'center' }}
  }
}
```

### 3.4 行内布局（水平排列）

```groovy
node('TicketRow', '37') {
  label '套餐行'
  props {
    string('lineMode') {{ 'single' }}
  }
  style('style') {
    number('paddingTop') {{ 12 }}
    number('paddingBottom') {{ 12 }}
  }
  slot('children') {
    node('TicketInfo', '37') {
      label '套餐信息'
      style('style') {
        number('flex') {{ 1 }}
      }
    }
    node('TicketStepper', '504') {
      label '数量选择'
    }
  }
}
```

---

## 四、Bad Case（错误示例）

### 4.1 ❌ 错误：使用 `styles { object('style') ... }`

**错误信息**：`Unexpected token "}" at xxx`

**错误写法**：

```groovy
node('SomeComponent', '123') {
  styles {
    object('style') {{
      string('backgroundColor') {{ '#FFFFFF' }}
    }}
  }
}
```

**正确写法**：使用 `style('styleName')` 语法

```groovy
node('SomeComponent', '123') {
  style('style') {
    string('backgroundColor') {{ '#FFFFFF' }}
  }
}
```

### 4.2 ❌ 错误：样式值类型不匹配

**问题**：数字类型的样式值使用了 `string()`

**错误写法**：

```groovy
style('style') {
  string('flex') {{ '1' }}
  string('marginBottom') {{ '10' }}
}
```

> ❌ `flex` 和 `marginBottom` 是数值类型，应使用 `number()`，不能用 `string()`

**正确写法**：

```groovy
style('style') {
  number('flex') {{ 1 }}
  number('marginBottom') {{ 10 }}
}
```

### 4.3 ❌ 错误：颜色值缺少引号

**问题**：颜色字符串在 Groovy 表达式中需要用单引号包裹

**错误写法**：

```groovy
style('style') {
  string('backgroundColor') {{ #FFFFFF }}
  string('borderColor') {{ E5E5E5 }}
}
```

> ❌ 颜色字符串在 `{{ }}` 内必须用单引号包裹，且 `#` 不能省略

**正确写法**：

```groovy
style('style') {
  string('backgroundColor') {{ '#FFFFFF' }}
  string('borderColor') {{ '#E5E5E5' }}
}
```

### 4.4 ❌ 错误：表达式格式错误

**问题**：忘记使用双大括号 `{{ }}`

**错误写法**：

```groovy
style('style') {
  number('marginBottom') 10
  string('backgroundColor') '#FFFFFF'
  number('flex') { 1 }
}
```

> ❌ 前两行缺少双大括号 `{{ }}`，第三行使用了单大括号 `{ }` 而非 `{{ }}`

**正确写法**：

```groovy
style('style') {
  number('marginBottom') {{ 10 }}
  string('backgroundColor') {{ '#FFFFFF' }}
  number('flex') {{ 1 }}
}
```

---

## 五、禁止 Case（严禁使用）

### 5.1 🚫 禁止：在样式中使用注释

DUO Groovy DSL **不支持任何注释**，注释会导致解析失败。

**禁止写法**：

```groovy
style('style') {
  number('marginBottom') {{ 10 }}
}
```

> ❌ 上方示例中原本包含 `// 这是注释` 和 `/* 这也是注释 */`，两种注释形式均会导致 DSL 解析失败，必须完全移除

**正确做法**：完全移除注释

```groovy
style('style') {
  number('marginBottom') {{ 10 }}
}
```

### 5.2 🚫 禁止：使用 JS/CSS 风格的样式语法

**禁止写法**：

```groovy
style('style') {
  string('margin') {{ '10px 20px' }}
  string('padding') {{ '16px' }}
  string('background') {{ 'rgb(255,255,255)' }}
}
```

> ❌ `margin` 不支持 CSS 简写，`padding` 不能带 `px` 单位（应为纯数字），`background` 不支持 RGB 格式（应用十六进制颜色字符串）

**正确写法**：

```groovy
style('style') {
  number('marginTop') {{ 10 }}
  number('marginBottom') {{ 10 }}
  number('marginLeft') {{ 20 }}
  number('marginRight') {{ 20 }}
  number('padding') {{ 16 }}
  string('backgroundColor') {{ '#FFFFFF' }}
}
```

### 5.3 🚫 禁止：使用 React Native 不支持的样式

DUO 基于 React Native，部分 CSS 样式不支持。

**禁止使用的样式**：

```groovy
style('style') {
  string('display') {{ 'block' }}
  string('position') {{ 'absolute' }}
  string('float') {{ 'left' }}
  string('lineHeight') {{ '1.5' }}
}
```

> ❌ `display` 和 `float` 在 React Native 中不支持；`position: absolute` 仅部分场景可用；`lineHeight` 应为 `number` 类型而非字符串

### 5.4 🚫 禁止：动态计算复杂样式值

**禁止写法**：

```groovy
style('style') {
  number('width') {{ DATA_SOURCE.data?.config?.width * 2 + 20 }}
  string('backgroundColor') {{ DATA_SOURCE.data?.theme === 'dark' ? '#000' : '#FFF' }}
}
```

> ❌ 禁止在 `style` 块内进行复杂计算或条件判断，应在 `dataSourceMap.groovy` 的 `currentData` 中预计算后再引用

**推荐做法**：在数据源 `currentData` 中预计算，或使用组件的 props 控制样式

在 `dataSourceMap.groovy` 中预计算：

```groovy
currentData {
  number('cardWidth') {{ DATA_SOURCE.data?.config?.width * 2 + 20 ?: 200 }}
  string('themeBgColor') {{ DATA_SOURCE.data?.theme === 'dark' ? '#000000' : '#FFFFFF' }}
}
```

在 `struct.groovy` 中使用：

```groovy
style('style') {
  number('width') {{ DATA_SOURCE.data?.cardWidth ?: 200 }}
  string('backgroundColor') {{ DATA_SOURCE.data?.themeBgColor ?: '#FFFFFF' }}
}
```

---

## 六、样式属性类型速查表

| 属性类型 | Groovy 类型声明 | 值格式 | 示例 |
|----------|-----------------|--------|------|
| 尺寸/数值 | `number()` | 数字 | `number('width') {{ 100 }}` |
| 颜色 | `string()` | 十六进制字符串 | `string('backgroundColor') {{ '#FF6600' }}` |
| 枚举值 | `string()` | 字符串 | `string('justifyContent') {{ 'center' }}` |
| 布尔值 | `bool()` | true/false | `bool('hidden') {{ false }}` |

---

## 七、常见问题排查

### Q1: 样式不生效

**排查步骤**：
1. 检查是否使用了正确的 `style('styleName')` 语法
2. 检查样式值类型是否匹配（number/string/bool）
3. 检查颜色值是否使用了 `'#RRGGBB'` 格式
4. 检查是否使用了 React Native 不支持的 CSS 属性

### Q2: 样式解析报错

**常见错误**：
- `Unexpected token "}"` → 检查是否使用了 `styles { object() }` 错误语法
- `Unexpected char "/"` → 检查是否使用了注释
- `Unknown identifier` → 检查样式属性名是否正确

### Q3: 布局异常

**常见原因**：
- 忘记设置 `flex: 1` 导致容器无法撑开
- 父容器没有设置 `flexDirection` 导致子元素垂直排列
- 使用了 CSS 简写语法（如 `margin: 10px`）
