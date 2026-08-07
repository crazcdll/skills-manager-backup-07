---
name: get-uuid
description: 通过 userId 或手机号查询用户 UUID（万能钥匙）。使用 raptorfe CLI（@mtfe/raptorfe-cli）的 masterkey 命令，支持查询用户在美团/点评等各 App 下的 UUID。触发词：查UUID、获取UUID、userId查UUID、手机号查UUID、万能钥匙、masterkey、base_uuid。
---

# get-uuid — 通过 userId / 手机号查询 UUID

## 查询决策流程

**判断用户是否已指定 App 和平台（iOS / Android / HarmonyOS）：**

- **已指定**：查「常用 app_name 表」找到对应 `app_name`，用 `--app-filters` 只搜目标 App 获取该用户真实 badge_id，再精确查询（见下方场景 A）。
- **未指定**：全量执行 `masterkey search` 获取所有 App 列表，取 ts 最大的条目，再精确查询（见下方场景 B）。

优先使用 **CLI 方式**，若报 `NO_COOKIE` 错误则自动切换到 **浏览器 evaluate 方式**。

---

## 方式一：CLI（raptorfe）

raptorfe 需使用默认 node 版本调用，鉴权自动通过大象 App 推送授权（缓存约 2.5 小时）。

### 场景 A：已知 App + 平台 → 两步查询（只查目标 App，比全量 search 快）

**第一步：用 `--app-filters` 只搜目标 App，获取该用户真实 badge_id**

```bash
raptorfe masterkey search --key <手机号或userId> --app-filters "<对应的app_name>"
```

从返回结果中取 `badge_id`。

**第二步：精确查询完整 UUID**

```bash
raptorfe masterkey user search \
  --key <手机号或userId> \
  --field-name base_uuid \
  --app <对应的app_name> \
  --badge-id <第一步取到的badge_id>
```

### 场景 B：未知 App → 两步查询

**第一步：全量搜索所有 App 的 badge 列表，找 ts 最大的条目，取其 app_name 和 badge_id**

```bash
raptorfe masterkey search --key <手机号或userId>
```

**第二步：精确查询完整 UUID**

```bash
raptorfe masterkey user search \
  --key <手机号或userId> \
  --field-name base_uuid \
  --app <ts最大的app_name> \
  --badge-id <ts最大的badge_id>
```

---

## 方式二：浏览器 evaluate（CLI 鉴权失败时使用）

**第一步：navigate 获取内网登录态（必须先执行，无需 UI 操作）**

```bash
~/.catpaw/bin/catdesk browser-action '{"action":"navigate","url":"https://perf.sankuai.com/perf/masterkey?isIframe=true&parentHost=raptor.mws.sankuai.com&cityId=1"}'
```

**第二步：evaluate 一次性查询所有 App 的完整 UUID（将 KEY 替换为手机号或 userId）**

```bash
~/.catpaw/bin/catdesk browser-action '{"action":"evaluate","script":"(async()=>{const searchResp=await fetch(\"https://perf.sankuai.com/badge/searchByJson\",{method:\"POST\",headers:{\"Content-Type\":\"application/json;charset=UTF-8\",\"x-requested-with\":\"XMLHttpRequest\"},body:JSON.stringify({key:\"KEY\",mp:false,appFilters:[\"com.sankuai.meituan\",\"com.meituan.imeituan\",\"com.sankuai.hmeituan\",\"com.dianping.v1\",\"com.dianping.dpscope\",\"com.sankuai.dianping\",\"com.sankuai.meituan.takeoutnew\",\"com.meituan.itakeaway\"]})});const list=await searchResp.json();const devices=list.map(item=>{const d=item.data?.[0];if(!d)return null;return{app:d.app_name,badgeId:d.badge_id,ts:d.ts,clientTime:d.clientTime};}).filter(Boolean);const results=await Promise.all(devices.map(async dev=>{const r=await fetch(\"https://perf.sankuai.com/badge/preciseValue?app=\"+dev.app+\"&badgeId=\"+dev.badgeId+\"&fieldName=base_uuid&key=KEY\",{headers:{\"x-requested-with\":\"XMLHttpRequest\"}});const uuid=await r.text();return{app:dev.app,uuid,ts:dev.ts,clientTime:dev.clientTime};}));results.sort((a,b)=>b.ts-a.ts);return JSON.stringify(results);})()"}'
```

返回结果已按最近活跃时间排序，第一条即为最近登录 App 的 UUID。

若返回 401 / null，说明浏览器 SSO 登录态已过期，重新执行第一步 navigate 后再试。

---

## 常用 app_name 表

| App 名称 | app_name | 平台 |
|---------|----------|------|
| 美团 iOS | `com.meituan.imeituan` | iOS |
| 美团 Android | `com.sankuai.meituan` | Android |
| 美团 HarmonyOS | `com.sankuai.hmeituan` | HarmonyOS |
| 大众点评 iOS | `com.dianping.dpscope` | iOS |
| 大众点评 Android | `com.dianping.v1` | Android |
| 大众点评 HarmonyOS | `com.sankuai.dianping` | HarmonyOS |
| 美团外卖 iOS | `com.meituan.itakeaway` | iOS |
| 美团外卖 Android | `com.sankuai.meituan.takeoutnew` | Android |
| Beam iOS | `com.sankuai.beam` | iOS |

> **注意**：badge_id 是设备维度的唯一标识，每台手机不同，**不能直接使用固定值**，必须先通过 `masterkey search` 或 `searchByJson` 查询该用户在目标 App 的真实 badge_id。iOS 和 Android 的 app_name 不同，美团 iOS 是 `com.meituan.imeituan`，美团 Android 是 `com.sankuai.meituan`，不要混淆。

---

## 输出规范

| 字段 | 值 |
|------|----|
| 名称 | App 名称（如：美团 iOS） |
| app_name | com.xxx.xxx |
| 系统 | iOS / Android / HarmonyOS |
| 版本 | x.x.x（如有） |
| 最近登录时间 | clientTime 字段值（如有） |
| UUID | 完整 UUID 值 |

---

## 注意事项

- badge_id 是设备维度的，每台手机不同，**不能用固定值**，必须先查询获取
- 已知 App + 平台时，用 `--app-filters` 只搜目标 App，**比全量 search 更快**
- `--badge-id` 为必传参数，需先通过 search 获取该用户在目标 App 的真实 badge_id
- `--app` 参数传 app_name（Bundle ID 字符串），不是数字 appId
- `ts` 字段为毫秒时间戳，取最大值即为最近登录的 App
- iOS 和 Android 同一产品的 app_name 不同，查询时注意区分
- 若所有 App 均无记录，说明该用户从未在这些 App 上登录过
- 查询其他字段（如 dpid）可用 `raptorfe masterkey field list` 查看所有可用字段
