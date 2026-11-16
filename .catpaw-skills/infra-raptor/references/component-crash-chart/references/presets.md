# 完整预设组件组


**美团：**

| group | 包含组件 |
|---|---|
| android:dsp | dsp-business, dsp-core |
| android:babel | metricx:babel |
| android:raptor | basemonitor |
| android:pike | pike, pike-knb-bridge |
| android:logan | networklog, clogan |
| android:common | ui, utils, native, storage, shortcut, permission, errorview |
| android:sniffer | metricx:sniffer |
| android:horn | horn 全系列 (9个) |
| ios:horn | SAKHorn |
| harmony:pike | @meituan/pike |
| harmony:horn | horn |

**点评（dp- 前缀）：**

| group | 包含组件 |
|---|---|
| dp-android:dsp/babel/raptor/pike/logan/horn/sniffer | 同上对应组件 |
| dp-ios:horn | SAKHorn |
| dp-harmony:pike | @meituan/pike |
| dp-harmony:horn | horn |

**外卖（wm- 前缀）：**

| group | project | 包含组件 |
|---|---|---|
| wm-android:babel | meituanwaimai | metricx:babel |
| wm-ios:horn | waimai_ios | SAKHorn |
| wm-ios:babel | waimai_ios | babel |
| wm-harmony:core | waimai-harmony | @machpro/core, @mach/core（主要 crash 组件） |
| wm-harmony:pike | waimai-harmony | @meituan/pike（接入量极少） |
| wm-harmony:babel | waimai-harmony | babel |

话术示例：
```
外卖 android babel crash 图         → wm-android:babel
外卖 iOS horn crash 图              → wm-ios:horn
外卖鸿蒙 crash 图                   → wm-harmony:core（主要 crash 组件）
外卖鸿蒙 pike crash 7天图           → wm-harmony:pike --range 7d
外卖 pike crash 版本对比 auto       → wm-harmony:pike --versions auto
```
