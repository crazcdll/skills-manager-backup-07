# struct 节点命名规则（重要）

## nodeName 必须页面内唯一

**错误信息**：`nodeName：LeezCard页面内不唯一`

**问题原因**：在 `node('NodeName', 'materialId')` 语法中：

- **第一个参数（nodeName）**：节点的唯一标识名称，必须在**整个页面内唯一**
- **第二个参数（materialId）**：物料 ID（componentsMap 的 key），同一物料的多个实例共用同一个 ID

**错误写法**：多个相同类型组件使用了相同的 nodeName

> ❌ 错误：三个 LeezCard 都叫 `'LeezCard'`，nodeName 重复

```groovy
node('LeezCard', '37') {
  label '商品信息卡片'
}
node('LeezCard', '37') {
  label '用户信息卡片'
}
node('LeezCard', '37') {
  label '底部提交栏'
}
```

**正确写法**：每个节点使用唯一的业务名称作为 nodeName

> ✅ 正确：每个节点使用唯一的业务名称作为 nodeName

```groovy
node('DealInfoCard', '37') {
  label '商品信息卡片'
}
node('UserInfoCard', '37') {
  label '用户信息卡片'
}
node('SubmitBarCard', '37') {
  label '底部提交栏'
}
```

## 命名规范建议

| 组件类型 | nodeName 命名建议 | 示例                                     |
| -------- | ----------------- | ---------------------------------------- |
| 文本组件 | 功能 + Text       | `DealNameText`, `PriceText`, `PhoneText` |
| 卡片组件 | 功能 + Card       | `DealInfoCard`, `UserInfoCard`           |
| 按钮组件 | 功能 + Button     | `SubmitButton`, `CancelButton`           |
| 布局组件 | 功能描述          | `MainLayout`, `TopBar`, `BottomBar`      |

## 与 label 的区别

| 属性                            | 用途                                   | 唯一性要求         |
| ------------------------------- | -------------------------------------- | ------------------ |
| `nodeName`（node 第一个参数）   | 节点的程序标识，用于事件通信、方法调用 | **必须页面内唯一** |
| `label`                         | 节点的显示名称，便于开发者识别         | 建议唯一，用于调试 |
| `materialId`（node 第二个参数） | 物料 ID，映射到 componentsMap          | 同一物料实例共用   |

**示例对照**：

```groovy
node('DealNameText', '38') {  // nodeName: 唯一标识（调用方法时使用）
  label '商品名称'            // label: 显示名称（便于识别）
  props {
    string('text') {{ DATA_SOURCE?.data?.dealName ?: '' }}
  }
}
```

**调用示例**：

> 通过 `nodeName` 调用其他节点的方法，使用 `nodeName` 而非 `label`

```groovy
on('onChange') {
  callMethod('DealNameText', 'updateValue')
}
```
