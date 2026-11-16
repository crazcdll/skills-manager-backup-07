# D2C 实战经验补丁

> 这些规则是在实际 D2C 开发中踩坑总结出来的，作为 max-preflight 规范的**补充**（不冲突时以 max-preflight 为准）。
> 派子 agent 时需内联到任务描述中。

---

## 1. line-height 与固定高度容器的调和

**场景**：单行文本标签（补贴 tag、状态 badge、价格符号等），容器有显式固定 height。

**问题**：max-preflight 要求 `line-height ≥ font-size × 1.3`，但设计稿中这类小标签往往 line-height = font-size，靠容器 padding 凑高度。如果强行加大 line-height 又不去 padding，容器会被撑高。

**规则**：
- 当容器有显式固定 `height` 且内部为**单行文本**时，`line-height` 可等于 `font-size`
- 去掉 padding-top / padding-bottom
- 用容器 `height` + `align-items: center` 垂直居中
- 多行文本（标题、描述、评论）仍严格遵守 `≥ 1.3`

**正确写法**：
```scss
.subsidy-tag {
  display: flex;
  flex-direction: row;
  align-items: center;
  justify-content: center;
  width: 89rpx;
  height: 28rpx;        /* 设计稿固定高度 */
  border-radius: 6rpx;
  padding-left: 6rpx;   /* 只保留水平 padding */
  padding-right: 6rpx;
}

.subsidy-text {
  font-size: 20rpx;
  line-height: 20rpx;   /* 单行+固定高度容器，允许 = font-size */
  color: #FFFFFF;
}
```

---

## 2. + 相邻选择器不可用

**场景**：想给"非第一个子元素"加 margin。

**问题**：Max/RN 不支持 CSS `+` 相邻兄弟选择器。

**规则**：
- 给需要不同样式的元素起独立 className（如 `.date-row-second`）
- 或者用 inline style `style={index > 0 ? { marginLeft: '12rpx' } : {}}` 动态加 margin

---

## 3. 子 agent 不要预消化数据

**场景**：主 agent 想把 inspect_node 结果整理好再给子 agent。

**问题**：主 agent 整理时会丢信息、理解偏差。子 agent 拿到的是二手信息。

**规则**：
- 给子 agent 提供 JSON 路径 + nodeId + inspect 命令
- 让子 agent **自己跑 inspect_node** 获取原始数据
- 主 agent 只提供：模块划分、CDN 切图表、编码规范

---

## 4. inline style 的 marginLeft/marginTop 用于列表间距

**场景**：map 渲染列表（卡片、按钮、筛选项），非首个需要间距。

**规则**：
- 用 `style={index > 0 ? { marginLeft: '12rpx' } : {}}` 给非首个子元素加间距
- 这不违反"className 必须是静态字符串"规则（style 是动态的，className 是静态的）
- 不要用 SCSS 写 `.item + .item { margin-left }` 或 `.item:not(:first-child)`

---

## 5. 设计稿 padding 与 line-height 的冲突判断

**快速判断公式**：
```
实际渲染高度 = max(line-height, font-size) + padding-top + padding-bottom
```

如果 `实际渲染高度 > 设计稿容器 height`，说明有冲突，需要：
1. 固定容器 height
2. 去掉 padding-top/bottom
3. align-items: center

---

_最后更新：2026-04-30_
