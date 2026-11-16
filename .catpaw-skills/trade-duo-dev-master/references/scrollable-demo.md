# 单文件竖向滚动 demo

## 参考文件与使用范围

[index.tsx](scrollable-demo/index.tsx) 是本次用户确认 iOS 滚动可用的完整组件示例，保留酒店与门票独立展示、单组、多组、空白项、长文本、证件兜底和本地校验。实例间距 24，尺寸按 375 口径。

将其作为目标组件包 `demo/index.tsx` 的参考：`../src/index` 与 `../src/types` 相对于组件包解析，在 references 内不能独立运行。其他组件需要按自己的真实 Props 和渲染分支准备数据，不能照搬酒店字段或覆盖已有有效场景。

## 为什么只设 flex: 1 不够

默认预览页的导航与内容是同级元素，内容容器设 `height: 100%` 时会在导航下再占整屏。ScrollView 仅使用 `flex: 1` 会继承过大的视口，最后一项无法完全滚入屏幕。

最终方案在 demo 内明确限制滚动视口，内部内容按自然高度增长。不要求其他同学手动修改预览页 Home，也不依赖原生布局测量或额外平台文件。

## index.tsx 内的高度约束

本次核对的 `@max/leez-navigation-bar@2.6.54` 默认 `theme.height=44`；预览 Home 使用 `safeArea='normal'`，未覆盖主题，其总高度包含顶部安全区。使用与导航同源的工具：

```tsx
import { remStyleSheet, toPx, toRem } from '@max/leez-style-util';
import { getBottomSpace, getSafeAreaMarginTop, getScreenHeight } from '@max/leez-internal-mix-util';

// 依据当前默认预览 NavigationBar，非任意页面通用高度。
const PREVIEW_NAVIGATION_BAR_HEIGHT = 44;
const previewScrollHeight = Math.max(
  0,
  getScreenHeight('window') - toPx(PREVIEW_NAVIGATION_BAR_HEIGHT)
    - getSafeAreaMarginTop() - getBottomSpace(),
);

const demoStyles = remStyleSheet({
  scroll: {
    height: toRem(previewScrollHeight),
    flexGrow: 0,
    flexShrink: 1,
  },
  container: { flexDirection: 'column' },
  section: { marginTop: 24 },
});
```

在现有渲染入口中使用：

```tsx
<ScrollView style={demoStyles.scroll}>
  <View style={demoStyles.container}>
    {/* 真实业务组件的独立场景实例，见完整 index.tsx */}
  </View>
</ScrollView>
```

- `getScreenHeight('window')`、顶部及底部安全区使用实际逻辑尺寸；`toPx(44)` 与导航内容的样式换算保持一致。
- 可用高度先经 `toRem` 转回样式工具的输入单位，再交给 `remStyleSheet`，不要再手工除以 2。
- `flexGrow: 0` 避免视口重新被撑大，`flexShrink: 1` 允许父区域更小时收缩。不要同时保留旧的 `flex: 1`。
- 内部内容 View 不设固定高度或 `flex: 1`，让多组内容自然撑开并滚动。
- 若目标导航主题、safeArea 模式、底部固定栏或框架不同，重新核对实际占用空间与工具单位，不机械照抄 44，不重复扣安全区。
- 示例在模块加载时计算高度，未覆盖旋转、多窗口等动态窗口变化；任务需要支持这些场景时，应依据框架能力更新高度并单独验证。

## 可分发性与验证

本次修复只需组件包的 `demo/index.tsx`，可正常重新运行 `duo preview-comp -t mrn`。该命令会重建 `~/.duo-cli/previewpage/src`，因此不要把共享 Home 的手动修改作为验收前提，也不要要求使用者先改预览环境。

原先的父容器 `height: 0; flex: 1` 修改能解决当前环境问题，但不会随 demo 分发；窗口坐标测量补丁也未解决本次真机问题。二者都不是本参考的推荐实现。

验证要求：

- 类型检查必须实际包含 demo；必要时使用临时配置纳入 demo，不修改业务类型制造通过。
- 通过正常命令重新生成预览，确认 demo 不依赖旧 Home 修改；滚到最底部，确认最后一个实例完整可见、可操作。
- 本地校验提示出现、内容变高后，再次检查底部可访问性。
- 本次单文件方案已由用户确认 iOS 可用；其他端、窗口变化和未执行的交互仍需分别验证，不以类型检查替代真机效果。
