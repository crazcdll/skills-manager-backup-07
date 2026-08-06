# 内置兜底：新架构目标版本（Citadel 不可用时使用）

> 与学城 [2738858921](https://km.sankuai.com/collabpage/2738858921) 同步维护；**执行时以 Citadel 拉取学城最新正文为准**，本表仅作离线/降级。

## RN 团队维护

| npm 包 | 目标版本 |
|--------|----------|
| @mrn/react-native | 5.1.3 |
| @mrn/mrn-base | 5.1.4 |
| @mrn/mrn-cli | 5.1.4 |
| @mrn/mrn-babel-preset | 5.1.4 |
| @mtfe/msi-mrn | 2.1.1 |
| @mtfe/msi | 2.1.1（与 msi-mrn 一致） |
| @mrn/react-native-blur-view | 1.0.3 |
| @mrn/react-native-skeleton-drawer | 2.0.0 |
| @mrn/react-native-shadow-view | 2.0.1 |
| @mrn/mrn-pull-refresh-loading-view | 1.0.6-test.1 |
| @mrn/react-native-linear-gradient | 2.0.1 |
| @mrn/react-native-pull-refresh | 2.0.0 |
| @mrn/mrn-page-view | 1.0.8-test.3 |
| @mrn/mrn-webview | 2.0.0-test.12 |
| @mrn/react-native-svg | 2.0.0-test.2 |
| @mrn/mrn-maskedview | 2.0.0 |
| @mrn/mvview | 2.0.0-test.0 |
| @mrn/mrn-msi-component | 2.0.1 |
| @mrn/mrnlottie | 5.0.0 |
| @mrn/react-navigation | 3.0.1 |
| @mrn/react-native-spring-scrollview | 2.0.0 |
| @mrn/mrn-bottom-sheet-view | 2.0.0-test.4 |
| @mrn/mrn-utils | 1.8.28-test.6 |
| @mrn/mrn-text | 2.0.0 |
| @mrn/mrn-text-input | 2.0.0 |
| @mrn/react-native-pager-view | 1.0.0 |
| react-native-gesture-handler | 2.29.1 |
| @mrn/react-native-safe-area-view | 2.0.1 |
| @mrn/mrn-privacy-api | 2.0.0 |
| @mrn/react-native-card-view | 2.0.0-test.3 |
| @mrn/mrn-touch-interceptor-view | 1.0.2 |
| @mrn/mrn-movable-view | 1.0.0-test.4 |
| @mrn/mrn-movable-area | 1.0.0-test.0 |
| react-native-webview | 13.16.0 |

## 外部团队

| npm 包 | 目标版本 |
|--------|----------|
| @ss/mtd-react-native | 1.0.1-beta.0 |
| @mrn/mrnmap | 4.1254.0-beta.206 |
| @mrn/mrn-blue | 1.0.5 |
| @mrn/mrn-ad-bridges | 1.0.11-beta.1 |
| @mrn/mlive-card | 2.0.1-dev.2 |

> 文档中 `@mrn/msi-mrn`（@mrn 前缀）为笔误，忽略。`@mrn/react-navigation-stack` 已弃用，不纳入。

## Max

| npm 包 | 目标版本 |
|--------|----------|
| @max/max-cli-standard | 0.0.35-beta.1 |
| @max/create-cli-utils | 2.0.5-xiaoyan06-328164.0 |
| @max/max-platform-transformer | 1.0.5-wangzhen174-328324.0 |
| @nibfe/mrn-babel-preset | 3.0.30-beta.1 |
| @max/build-mrn-dependencies | 2.0.1-xiaoyan06-328324.0 |
| @max/css-transformer-px | 1.0.5-xiaoyan06-328324.0 |
| @max/css-transformer | 1.0.3-xiaoyan06-328324.0 |

## 固定（不受学城表左右）

| npm 包 | 版本 |
|--------|------|
| react | 19.1.1 |
| react-redux | 9.2.0 |
| redux | 5.0.1 |

## 规则摘要

- 标注「无需升级」「待补充」等或**无有效版本**的包：**不**纳入目标集。
- `@mtfe/msi` 与 `@mtfe/msi-mrn` **必须**同版本。
