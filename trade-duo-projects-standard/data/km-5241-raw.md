# 标准化公共依赖版本-整合版

1. 业务独立的npm可以放到子目录下。
2. 可通过[Skill: standardization-deps（standardization-deps）](https://friday.sankuai.com/mcp/skill-detail?activeTab=overview&from=/skills-market?deepseek=false%26keyword=standardization-deps%26orderByDownloadCount=all%26orderByTotalCallCount=all%26orderByTotalCallerCount=all%26page=1%26pageSize=30%26tag=%26verifiedType=all%26viewMode=card%26visibility=all&id=5727)，录入wiki地址和【已完成标准化的仓库地址】，让助手自动录入。


| 依赖名称| 版本号| 三个系统兼容| 是否废弃| 无需鸿蒙适配| 备注|
|---|---|---|---|---|---|
| @mrn/hoteltravel-common| 1.235.1-beta.18| ✅@max/meituan-uni| ❌| ❌| 注意msi版本一定要大于@mtfe/msi-mrn 1.88.1-alpha.dde54cc2.0、@mtfe/msi  1.88.1-alpha.dde54cc2.0    需要额外锁包："@max/meituan-uni-screenInfo": "0.0.1-beta.24"    若出现'MonitoredVideoPlayerView'相关的报错，说明使用了旧版本的播放器，需咨询@殷嘉铖进行替换|
| @nibfe/cross-base| 0.37.0| ✅| ❌| ❌| 目前0.37.0版本处理了msi桥，还有MRNpageview处理中|
| @nibfe/elink-sdk-mrn| 0.0.11-beta.0| ✅| ❌| ❌| ~~@max/meituan-uni-network和@max/meituan-uni-navigate暂未更新，先锁定~~  ~~@nibfe/~~[elink-sdk-mrn@0.0.11](mailto:elink-sdk-mrn@0.0.11)~~-beta.0~~  ~~@nibfe/elink-sdk-max@0.1.6-beta.0~~|
| @hfe/member-growth-value-alone| 1.0.67| ✅| ❌| ❌| @mtfe/msi、@mtfe/msi-mrn版本>=1.80.1|
| @mrn/hotel-hp-player-common| 3.1.1-beta.1| ✅| ❌| ❌| 直接升级版本即可，需要回归 美团、点评、Android、iOS、Harmony。  核心回归能力  1、无缝续播  2、播放、暂停过程中封面图展示与否，全部播放完后重新播放，前后台切换，静音切换。|
| @mrn/hotel-hp-player| 1.35.0| ✅| ❌| ❌| |
| @react-native-oh-tpl/react-native-slider| ^0.11.0-0.1.5| ✅| ❌| ❌| |
| deprecated-react-native-prop-types| 4.0.0| ✅| ❌| ❌| |
| @mrn/hotel-hp-player-component| 1.36.0| ✅| ❌| ❌| |
| @mrn/rn-video-float-viewer| 1.1.33| ✅| ❌| ❌| |
| @mrn/mlive-card| 0.1.9| ✅| ❌| ❌| |
| @hfe/rn-hotel-cross-component| 1.51.0| ✅| ❌| ❌| |
| @mrn/ai-common  | 1.18.0| ✅| ❌| ❌| |
| @zhenguo/modules  | 3.7.33| ✅| ❌| ❌| |
| @zhenguo/mrn-ironbox| 3.4.175| ✅| ❌| ❌| |
| @mrn/hotel-calendar| 3.92.0| ✅| ❌| ❌| |
| @hfe/hoteltravel-dateutils| 0.21.0| ✅| ❌| ❌| |
| @hfe/hoteltravel-datecheck| 1.56.1-beta.5| ✅| ❌| ❌| |
| @hfe/hotel-context-module| 0.4.1-beta.5| ✅| ❌| ❌| |
| @mrn/mrn-cli| ^4.0.1| ❌| ❌| ❌| 该版本仅鸿蒙可用|
| @mrn/mrn-base| ^4.0.5| ❌| ❌| ❌| 该版本仅鸿蒙可用|
| @mrn/react-native| ^4.0.3| ❌| ❌| ❌| 该版本仅鸿蒙可用|
| @mrn/mrn-utils| ^1.8.26| ✅| ❌| ❌| |
| @mrn/react-navigation| ^2.9.25| ✅| ❌| ❌| |
| @mtfe/msi-mrn| 1.81.0-beta.0| ✅| ❌| ❌| |
| @mtfe/msi| 1.81.0-beta.0| ✅| ❌| ❌| |
| @mrn/mrnlottie| 4.0.1| ✅| ❌| ❌| |
| @ss/mtd-react-native| 0.4.12| ✅| ❌| ❌| |
| @mrn/react-native-linear-gradient| 1.1.8| ✅| ❌| ❌| |
| @analytics/mrn-sdk| 1.8.1| ✅| ❌| ❌| |
| @mrn/mrn-owl| 2.0.0| ✅| ❌| ❌| |
| @mrn/rn-danmaku| 全部版本| ✅| ❌| ❌| |
| @mrn/auto-height-image| 全部版本| ✅| ❌| ❌| |
| @mrn/mrn-privacy-api| 1.0.15| ✅| ❌| ❌| |
| @mrn/react-native-safe-area-view| 0.14.15| ✅| ❌| ❌| |
| @mrn/react-navigation-stack| 2.0.1-beta.0| ✅| ❌| ❌| |
| @mrn/react-native-pull-refresh| 1.0.3-beta.4| ✅| ❌| ❌| |
| @mrn/react-native-blur-view| 1.0.2| ✅| ❌| ❌| |
| @mrn/react-native-skeleton-drawer| 1.0.5| ✅| ❌| ❌| |
| @mrn/react-native-shadow-view| 1.0.3-beta.1| ✅| ❌| ❌| |
| @mrn/react-native-spring-scrollview| 1.0.2| ✅| ❌| ❌| |
| @mrn/mvview| 1.1.2| ✅| ❌| ❌| |
| @mrn/mrn-text| 1.0.9| ✅| ❌| ❌| |
| @mrn/mrnmap| 4.1240.0| ✅| ❌| ❌| |
| @mrn/mrn-blue| 1.0.4| ✅| ❌| ❌| |
| @mrn/mrn-ad-bridges| 1.0.10| ✅| ❌| ❌| |
| @mtfe/minor-mode-popup-mrn| 2.0.0| ✅| ❌| ❌| ~~替换成@react-native-oh-tpl/react-native-safe-area-context~~|
| @mrn/mrn-page-view| 1.0.7| ❌| ❌| ❌| 部分属性兼容[鸿蒙MRNPageView组件开发](https://km.sankuai.com/collabpage/2713971700)|
| @nibfe/doraemon-practice| 3.2.6| ❌| ❌| ❌| |
| @mrn/mrn-webview| 1.0.5| ✅| ❌| ❌| |
| @react-native-oh-tpl/react-native-webview| 13.10.2-0.2.23| ❌| ❌| ❌| |
| react-native-text-ticker| 1.15.0| ❌| ❌| ❌| |
| @max/builder-user-config| 2.0.4| ✅| ❌| ❌| |
| @max/meituan-uni-utils| 2.0.4| ✅| ❌| ❌| 使用适配层必备|
| @max/meituan-uni-mrnUtils| 2.0.4| ✅| ❌| ❌| |
| @max/meituan-uni-knb| 2.0.14| ✅| ❌| ❌| 使用适配层必备|
| @max/meituan-uni-env| 1.1.3| ✅| ❌| ❌| 判断环境必备|
| @max/create-cli-utils| 2.0.4| ✅| ❌| ❌| |
| @max/babel-preset-max-alias| 0.0.4| ✅| ❌| ❌| 使用适配层必备|
| @max/build-plugin-hotel-adaptor| 1.0.8| ✅| ❌| ❌| |
| @max/babel-plugin-hotel-adaptor| 1.0.7| ✅| ❌| ❌| |
| @max/hotel-travel-mrn-adaptor| 1.0.6| ✅| ❌| ❌| |
| @max/leez-icon| 2.6.11| ❌| ❌| ❌| 鸿蒙上不支持字体形式的返回按钮|
| @max/leez-modal-base-container| 2.6.65| ✅| ❌| ❌| |
| @hfe/max-webview| 4.0.1| ✅| ❌| ❌| |
| @max/meituan-uni-lx| 2.0.2| ✅| ❌| ❌| |
| @max/meituan-uni-pay| 2.0.2| ✅| ❌| ❌| |
| @max/meituan-uni-envInWeb| **0.0.9**| ✅| ❌| ❌| |
| @max/meituan-uni-login| 2.0.2| ✅| ❌| ❌| |
| @max/meituan-uni-screenInfo| 2.0.1| ✅| ❌| ❌| |
| @max/meituan-uni-fingerprint| 2.0.2| ✅| ❌| ❌| |
| @max/meituan-uni-image| 2.0.2| ✅| ❌| ❌| |
| @max/meituan-uni-event| 3.0.2| ✅| ❌| ❌| |
| @max/meituan-uni-network| 4.0.2| ✅| ❌| ❌| |
| @max/meituan-uni-contact| 1.0.1| ✅| ❌| ❌| |
| @max/meituan-uni-screen| 2.0.1| ✅| ❌| ❌| |
| @max/meituan-uni-location| 2.0.1| ✅| ❌| ❌| |
| @max/meituan-uni-city| 2.0.1| ✅| ❌| ❌| |
| @max/meituan-uni-mtShare| 2.0.1| ✅| ❌| ❌| |
| @max/meituan-uni-navigate| 2.0.1| ✅| ❌| ❌| |
| @max/meituan-uni-setting| 2.0.1| ✅| ❌| ❌| |
| @max/meituan-uni-system| 2.0.2| ✅| ❌| ❌| |
| @max/meituan-uni-userInfo| 2.0.1| ✅| ❌| ❌| |
| @max/meituan-uni-authorize| 2.0.1| ✅| ❌| ❌| |
| @max/meituan-uni-report| 1.0.6| ✅| ❌| ❌| |
| @hfe/max-\* 系列组件（button、image、text、view 等）| 4.0.0| ✅| ❌| ❌| |
| @hfe/max-universal-xx系列| 2.0.3| ❌| ❌| ❌| 已经废弃，需要提醒用户替换为maxAPI|
| @max/leez-dependencies 等leez相关依赖| 2.6.73| ✅| ❌| ❌| |
| @mrn/mrn-knb| 0.5.1| ❌| ✅| ❌| 鸿蒙上不支持KNB，需要提醒开发者推动下线|
| @max/build-miniapp-dependencies| 2.0.3| ✅| ❌| ❌| |
| @max/build-mrn-dependencies| 2.0.1| ✅| ❌| ❌| |
| @max/build-plugin-max-component| 2.1.9| ✅| ❌| ❌| |
| @max/build-plugin-miniapp-publish| 1.0.0| ✅| ❌| ❌| |
| @max/build-web-dependencies| 2.0.3| ✅| ❌| ❌| |
| @max/eslint-plugin-max-compile-time-miniapp| 1.0.22| ✅| ❌| ❌| |
| @max/kit-lib-build-config-helper| 1.0.8| ✅| ❌| ❌| |
| @max/max-app| 2.0.8| ✅| ❌| ❌| |
| @max/max-base-dev-dependencies| 1.0.3| ✅| ❌| ❌| |
| @max/max-miniapp-build-error-helper-plugin| 1.0.4| ✅| ❌| ❌| |
| @max/max-spec| 1.0.3| ✅| ❌| ❌| |
