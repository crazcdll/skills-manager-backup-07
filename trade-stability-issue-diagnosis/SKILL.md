---
name: trade-stability-issue-diagnosis
description: >
  交易前端问题排查专家，覆盖餐（meishi）、综（gc）、酒（hotel）、景（travel）四条业务线，支持美团/点评 APP、美小/点小程序、H5/i版全端。
  排查流程：收集信息 → 匹配研发资产（页面/Bundle/技术栈）→ 并行查日志与发布记录 → 汇总分析 → 输出结构化结论。
  技术栈覆盖：DUO、MRN、MAX、小程序、H5；支持 iOS / Android / Harmony。
  用户标识自适应：userId 或手机号走 UUID 查询路径（前端异常 + 后端日志双线并行）；traceId / 订单号 / openId 直接定位后端链路；无标识时通过发布变更分析。
  查询能力：万能钥匙查 UUID、Raptor 前端异常、Logan 端侧日志回捞、后端日志（topic）、Diva 发布变更、git diff 代码分析。
  输出：结构化排查结论表，含结论定性（有效/无效/待确认）、根因日志、关联变更版本、修复建议和负责人。
  触发词：交易问题排查、线上问题、TT工单、用户反馈、餐综酒景、提单异常、提单失败、支付失败、支付异常、退款问题、页面白屏、功能不可用、userId排查、traceId排查、订单号排查、查UUID、查日志、前端异常排查、bundle问题、发布回归、查询bundle的发布记录。
skill-dependencies:
  - name: mtsso-skills-official
    # 按需声明，只写你实际用到的票据类型
    # 如果需要应用身份票据，声明此项：
    app_access_token_placeholder: ${app_access_token}
    
    # 如果需要用户身份票据，声明此项：
    user_access_token_placeholder: ${user_access_token}
    audience: "60921859"
    prompt: 本技能所需的token 占位符，请参考mtsso-skills-official的相关说明进行获取和注入

metadata:
  skillhub.creator: "bijietao"
  skillhub.updater: "bijietao"
  skillhub.version: "V5"
  skillhub.source: "FRIDAY Skillhub"
  skillhub.skill_id: "28959"
  skillhub.high_sensitive: "false"
---

# 交易前端问题排查

**排查流程**：收集信息 → 匹配页面 → 查日志 & 查发布记录（并行）→ 汇总分析 → 输出结论

---

## 环境检查

> ⚠️ 排查流程中会自动校验并安装/更新 CLI，通常无需手动执行以下命令。仅在自动安装失败时参考。

```bash
# 确保 mtskills 可用
mtskills --version 2>/dev/null || npm i -g @mtfe/mtskills --registry=http://r.npm.sankuai.com
```

各 CLI 工具的详细安装步骤，参见对应排查流程文档中的「环境检查」章节。

---

## 排查流程

### 第一步：收集用户信息

**如果用户没有主动提供足够信息，一次性发出以下提问**（不要分多条问）：

> 请提供以下信息，有什么填什么，没有的可以跳过：
> 1. **业务方向**（必填）：餐 / 综 / 酒 / 景
> 2. **用户标识**（必填）：userId、手机号、订单号、UUID、openId、traceId 任一均可
> 3. **问题描述**（必填）：文字描述或截图
> 4. **发生时间**（选填）：默认查最近 24 小时
> 5. **客户端 / 系统**（选填）：美团/点评/美小/点小/H5，iOS/Android/Harmony

**收到信息后的处理规则**：

- **方向未填**：禁止继续，提示用户从「餐/综/酒/景」中选一个
- **无用户标识（userId/手机号等）**：必须补充用户标识，否则无法查询

---

### 第二步：匹配问题页面

根据用户截图或描述，在研发资产映射表中匹配对应页面。

**餐读取** [references/assets/food-dev-assets.md](references/assets/food-dev-assets.md) 获取完整映射数据。
**综读取** [references/assets/gc-dev-assets.md](references/assets/gc-dev-assets.md) 获取完整映射数据。
**酒读取** [references/assets/hotel-dev-assets.md](references/assets/hotel-dev-assets.md) 获取完整映射数据。
**景读取** [references/assets/travel-dev-assets.md](references/assets/travel-dev-assets.md) 获取完整映射数据。

**匹配策略**：
1. 优先根据截图特征（标题、按钮、布局）匹配
2. 其次根据关键词匹配（提单→团购提单，支付结果→支付结果页，订单详情→订单详情页，退款→申请退款）
3. 注意区分技术栈版本（DUO/MRN/MAX/小程序/H5），根据客户端信息判断
4. 无法确定时，列出候选页面让用户确认

**获取信息**：页面名称、技术栈、bundle名、仓库链接、diva发布链接、projectId、前端raptor异常链接、后端日志 topic（可能有多个）

---

### 第三步：排查日志和发布记录

根据客户端类型选择对应排查流程：

**移动端 APP（美团 APP / 点评 APP）**：

读取 [references/app-client-investigation.md](references/app-client-investigation.md) 执行排查。根据用户提供的信息选择入口：
- 提供了 **userId 或手机号** → 线路 A（A1 查前端异常 → A2 查后端日志）与线路 B（Diva 发布记录 → 代码变更分析）**并行**推进
- 提供了 **traceId / 订单号 / dealID / openID** → 跳过 A1，直接从 A2 查后端日志；同时并行推进线路 B
- **以上均未提供** → 跳过线路 A，仅执行线路 B 查发布记录

> 任意一条线路得出明确结论即可停止另一条，直接进入第五步输出。

**小程序 & H5（美小 / 点小 / DUO 转 H5 / MAX 转 H5 / i 版）**：

读取 [references/miniapp-investigation.md](references/miniapp-investigation.md) 执行排查。小程序和 H5 均无 UUID，只查后端日志，无线路 B。根据用户提供的信息选择入口：
- 提供了 **userId 或手机号** → 直接查后端日志
- 提供了 **traceId / 订单号 / dealID / openID** → 以对应字段查后端日志
- **以上均未提供** → 无法查日志，提示用户补充 userId 或手机号

> 有结论直接进入第五步。

---

### 第四步：汇总排查结果

> 仅适用于移动端 APP（有线路 A + B 两条线）。小程序 & H5 只有线路 A，有结论直接进入第五步。

| 情况 | 处理方式 |
|------|---------|
| 线路 A 有结论，线路 B 无结论 | 以日志报错为根因，进入第五步 |
| 线路 B 有结论，线路 A 无结论 | 以发布变更为根因，进入第五步 |
| 两条线均有结论 | 综合分析，判断主因，进入第五步 |
| 两条线均无结论 | 延长时间窗口重查，或提示用户补充 userId / 手机号 |

---

### 第五步：输出排查结论

严格按以下格式输出（表格）：

| 字段 | 内容 |
|------|------|
| **结论** | ✅ 有效问题 / ❌ 无效问题（误报）/ ⚠️ 待进一步确认 |
| **用户信息** | UUID / userId / 手机号 |
| **问题时间** | YY-MM-DD HH:mm:ss ~ YY-MM-DD HH:mm:ss 或 YY-MM-DD HH:mm:ss |
| **问题页面** | 页面名称 + 技术栈 + bundle |
| **仓库地址** | 仓库链接 |
| **日志分析** | raptor 异常或后端日志中的关键错误，需包含 traceId |
| **变更版本** | 版本号 + 发布时间 + commit hash |
| **变更内容** | 变更组件/代码描述（DUO 填组件名+版本，MRN/MAX 填变更文件+摘要） |
| **其他建议** | 修复建议或进一步排查方向 |
| **负责人** | 餐/毕杰涛 综/徐俊 酒/鲍立磊 景/王松 |

---

## 辅助工具

读取 [references/useful-links.md](references/useful-links.md) 获取完整工具链接。

**常用工具速查**：

| 用途 | 链接 |
|------|------|
| 万能钥匙（查 UUID） | https://perf.sankuai.com/perf/masterkey/searchresult |
| 用户信息（查 openId） | https://admin-user.sankuai.com/service/normal/userinfo |
| Yooz 组件平台 | https://yooz.sankuai.com/client-platform/material/component |
| 订单查询 | https://admin-ordercenter.sankuai.com/order/index.html |
| 订单全景 | https://watson.sankuai.com/mptrade/fullview |
| 风控查询 | https://mtsi.mws.sankuai.com/complaint_cust_serv |
| 反扒查询 | https://mtsi.mws.sankuai.com/strategy_hit |
| 移动端 Logan 日志回捞 | https://logan.mws.sankuai.com/grab |
| 美团小程序实时日志 | https://logan.mws.sankuai.com/rtl/web?tab=advancedQuery&categoryId=38 |
| 网关日志 | https://oceanus.mws.sankuai.com/site_detail?site_name=rpc.meituan.com&site_id=10157&tab=log-select |

---

## 注意事项

- 移动端 APP 两条排查线路并行推进，任意一条得出明确结论即可停止另一条，避免无效等待
- 小程序 & H5 无 UUID，直接用 userId 或手机号查后端日志，无需并行
- DUO 页面优先分析 componentsMap.json，MRN/MAX 页面直接 git diff 全量代码
- 所有仓库 clone 到 `/Users/All_deal_project/` 目录下
- 浏览器操作优先使用可见文本和语义定位元素
