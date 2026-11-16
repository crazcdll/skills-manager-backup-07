---
name: diva-bundle-version-query
description: Queries Diva bundle version history to identify the problematic version during incident investigation. Given a bundle name and an incident time, it determines the active version at that time, retrieves its commit hash and the previous version's commit hash for code diff analysis. Also supports checking whether any deployment occurred in the past N days. Use when investigating alerts, diagnosing production issues, or performing post-deployment inspections. Trigger keywords: Diva 版本查询、定位问题版本、查发布记录、获取 commit hash、告警关联变更、48小时发布、近5天无发布、diva bundle 版本。
---

# Diva Bundle 版本查询 — 问题版本定位

## 使用场景

告警排查时，需要判断：
1. 最近 N 天内是否有发布（无发布则排除变更因素）
2. 问题时间对应的「生效版本」是哪个（即问题发生时已上线的最新版本）
3. 获取该版本及上一版本的 commit hash，供代码 diff 分析

## 执行流程

### Step 1：导航到 Diva 获取登录态

```js
// browser navigate
navigate("https://diva.sankuai.com")
```

### Step 2：调用 listVersion API 获取版本列表

```js
// 用 evaluate + fetch 调用，浏览器自动携带 Cookie
const result = await fetch(
  "https://diva.sankuai.com/api/bundle/listVersion?" + new URLSearchParams({
    bundleName: "<BUNDLE_NAME>",   // 如 rn_meishi_smart-order-food-submit
    env: "prod",
    keyword: "",
    pageIndex: "1",
    pageSize: "50",                // 拉多一些确保覆盖 5 天范围
    ssoprotect: "1"
  })
).then(r => r.json());
```

返回字段说明（每条版本记录）：

| 字段 | 说明 |
|------|------|
| `version` | 版本号，如 `0.68.0` |
| `publishTime` | 上线时间（毫秒时间戳 或 格式化时间串） |
| `commitHash` | 该版本对应的 git commit hash |
| `status` | 版本状态（online / offline 等） |

> 列表默认按发布时间**倒序**排列，第 0 条为最新版本。

### Step 3：判断「最近 5 天无发布」

```js
const fiveDaysAgo = Date.now() - 5 * 24 * 60 * 60 * 1000;
const recentVersions = result.data.list.filter(v => 
  new Date(v.publishTime).getTime() >= fiveDaysAgo
);

if (recentVersions.length === 0) {
  // 输出：近 5 天无发布，变更因素可排除
}
```

### Step 4：根据问题时间定位问题版本

```js
// problemTime: 问题发生时间（ms timestamp 或 可解析的时间字符串）
const problemTs = new Date("<PROBLEM_TIME>").getTime();

const versions = result.data.list; // 已按 publishTime 倒序
// 找到 publishTime <= problemTs 的第一条（即问题发生时已生效的最新版本）
const problemVersion = versions.find(v => 
  new Date(v.publishTime).getTime() <= problemTs
);
// 下一条即为上一个版本
const prevVersion = versions[versions.indexOf(problemVersion) + 1];
```

### Step 5：获取单版本详情（含完整 commit hash）

若 listVersion 返回的 commitHash 是缩写，用此接口补全：

```js
const detail = await fetch(
  "https://diva.sankuai.com/api/bundle/singleVersion?" + new URLSearchParams({
    bundleName: "<BUNDLE_NAME>",
    env: "prod",
    version: "<VERSION>",
    ssoprotect: "1"
  })
).then(r => r.json());
// detail.data.commitHash — 完整 commit hash
```

### Step 6：输出结论

按如下格式输出：

```
【发布情况】近 5 天内有/无发布，共 X 个版本
【问题版本】<version>
  - 上线时间：<publishTime>
  - commitHash：<hash>
  - Devtools 链接：https://dev.sankuai.com/code/repo-detail/<org>/<repo>/commit/<hash>
【上一版本】<prevVersion>
  - 上线时间：<prevPublishTime>
  - commitHash：<prevHash>
【Diff 链接】https://dev.sankuai.com/code/repo-detail/<org>/<repo>/compare/<prevHash>...<hash>
```

## 常用 Bundle 与仓库映射

| Bundle | 仓库路径（dev.sankuai.com） |
|--------|---------------------------|
| rn_meishi_smart-order-food-submit | meis/smart-ordering |
| rn_meishi_* | meis/* |
| rn_gc_* | gc/* |
| rn_hotel_* | hotel/* |

> 实际仓库路径可从 Diva 版本详情页的 commit 链接中提取。

## 参数说明

| 占位符 | 说明 | 示例 |
|--------|------|------|
| `<BUNDLE_NAME>` | Diva bundle 名称 | `rn_meishi_smart-order-food-submit` |
| `<PROBLEM_TIME>` | 问题发生时间 | `2026-04-22 10:30:00` |
| `<VERSION>` | 版本号 | `0.68.0` |

## 注意事项

- URL 中的动态安全参数（`mtgsig`、`u2dhn6k` 等）由页面 JS 自动生成，**直接调用 fetch 无需手动传**，浏览器会处理
- 若 `ssoprotect=1` 导致 401，先 `navigate` 到 `https://diva.sankuai.com` 刷新登录态再重试
- pageSize 建议设为 50，确保覆盖足够的历史版本
