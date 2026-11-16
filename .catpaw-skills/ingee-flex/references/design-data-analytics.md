# Ingee 视觉稿数据分析规则

## 结构布局分析规则
1. 视觉稿的整体布局结构不能单纯依赖数据读取，需要结合视觉稿数据结构与物料图片分析结果进行最终位置确认，保证物料位置和层级的准确性。

## 视觉样式分析规则

> 详细规则见 [references/flex-design-gen.md](flex-design-gen.md)「规则要求」章节，以下为关键摘要：

1. 当视觉稿中声明 display: flex; flex-direction: row; align-items: center; 但未声明 justify-content 时，默认使用 justify-content: flex-start。
2. 设计稿尺寸需缩放一半：如设计稿 100px 对应代码 50px。
3. 视觉稿中的 gap 属性在 Max 技术栈中**不允许使用**，须将 gap 转换为子元素的 margin-bottom（纵向）或 margin-right（横向）。