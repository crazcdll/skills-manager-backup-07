# KNB → MSI 迁移说明文档表

供 MSI 使用情况走查时对照：用到的 MSI API 在此表中查找对应 KM 文档链接，打开文档后按「入参差异」「出参差异」等做合规检查。

## 迁移关系与文档链接

| 迁移关系（KNB → MSI/其他） | 文档链接 |
|---------------------------|----------|
| KNB.addRequestSignature → MSI.addRequestSignature | https://km.sankuai.com/page/2728485142 |
| KNB.autoLock → MSI.setKeepScreenOn | https://km.sankuai.com/page/2728544705 |
| KNB.capture → MSI.capture | https://km.sankuai.com/page/2728922313 |
| KNB.chooseFile → MSI.chooseFile | https://km.sankuai.com/page/2728724342 |
| KNB.chooseImage → MSI.chooseImage | https://km.sankuai.com/page/2728694391 |
| KNB.chooseVideo → MSI.chooseVideo | https://km.sankuai.com/page/2729190793 |
| KNB.clearStorage → MSI.removeSharedStorage | https://km.sankuai.com/page/2729041745 |
| KNB.closePageWithKeys → MSI.closePageWithKeys | https://km.sankuai.com/page/2729121116 |
| KNB.closePage → MSI.closePage | https://km.sankuai.com/page/2728734247 |
| KNB.closeWebview → MSI.closePage | https://km.sankuai.com/page/2728744248 |
| KNB.closeWindow → MRNUtils.pageRouterClose | https://km.sankuai.com/page/2728705623 |
| KNB.compressImage → MSI.compressImage | https://km.sankuai.com/page/2729141379 |
| KNB.configShare → MSI.setRRButton、mtShare | https://km.sankuai.com/page/2729240498 |
| KNB.connectWifi → MSI.connectWifi | https://km.sankuai.com/page/2728694456 |
| KNB.decryptData → MSI.decrypt | https://km.sankuai.com/page/2728485241 |
| KNB.downloadImage → MSI.downloadFile、saveImageToPhotosAlbum | https://km.sankuai.com/page/2728614665 |
| KNB.encryptData → MSI.encrypt | https://km.sankuai.com/page/2728515267 |
| KNB.getAccessibilityStatus → MSI.checkIsOpenAccessibility | https://km.sankuai.com/page/2729011963 |
| KNB.getAppInfo → MSI.getSystemInfo | https://km.sankuai.com/page/2728744322 |
| KNB.getBrightness → MSI.getScreenBrightness | https://km.sankuai.com/page/2729021939 |
| KNB.getCity → MSI.getCityInfo/getSelectedCityInfo | https://km.sankuai.com/page/2728515274 |
| KNB.getClipboard → MSI.getClipboardData | https://km.sankuai.com/page/2728604692 |
| KNB.getDeviceInfo → MSI.getDeviceInfoAsync、getBatteryInfo | https://km.sankuai.com/page/2729041815 |
| KNB.getFingerprint → MSI.getRiskControlFingerprint | https://km.sankuai.com/page/2729180736 |
| KNB.getImageInfo → MSI.getImageInfo | https://km.sankuai.com/page/2728912557 |
| KNB.getLocation → MSI.onLocationChange、startLocationUpdate、getLocation | https://km.sankuai.com/page/2729091379 |
| KNB.getMediaFrame → MSI.getVideoFirstFrame | https://km.sankuai.com/page/2729151069 |
| KNB.getNetworkTime → MSI.getNetworkTime | https://km.sankuai.com/page/2728485282 |
| KNB.getNetworkType → MSI.getNetworkType | https://km.sankuai.com/page/2728783072 |
| KNB.getPageState → MSI.onAppStatusChange | https://km.sankuai.com/page/2728584800 |
| KNB.getResult → MSI.getPageResult | https://km.sankuai.com/page/2728644519 |
| KNB.getSafeArea → MSI.getSystemInfoAsync | https://km.sankuai.com/page/2729260257 |
| KNB.getServiceInfo → MSI.getServiceInfo | https://km.sankuai.com/page/2729011992 |
| KNB.getStorage → MSI.getSharedStorage | https://km.sankuai.com/page/2728773139 |
| KNB.getUserInfo → MSI.getUserInfo | https://km.sankuai.com/page/2729031627 |
| KNB.getWifiInfo → MSI.getConnectedWifi、startWifi | https://km.sankuai.com/page/2729280093 |
| KNB.getWifiList → MSI Wi-Fi 相关 API | https://km.sankuai.com/page/2729280095 |
| KNB.getWifiSwitchStatus → MSI.getSystemInfoAsync | https://km.sankuai.com/page/2728694587 |
| KNB.isApiSupported → MSI.canIUse | https://km.sankuai.com/page/2728773213 |
| KNB.isInstalledApp → MSI.isAppsInstalled | https://km.sankuai.com/page/2729052018 |
| KNB.jumpPage → MSI.jumpToLink | https://km.sankuai.com/page/2728664622 |
| KNB.jumpToScheme → MRNUtils.openUrl | https://km.sankuai.com/page/2729102421 |
| KNB.knb.shortcut.add → MSI.addShortcut | https://km.sankuai.com/page/2728704530 |
| KNB.knb.shortcut.delete → MSI.deleteShortcut | https://km.sankuai.com/page/2728783136 |
| KNB.knb.shortcut.query → MSI.queryShortcut | https://km.sankuai.com/page/2728584898 |
| KNB.knb.shortcut.update → MSI.updateShortcut | https://km.sankuai.com/page/2729171087 |
| KNB.login → MSI.login、getUserInfo | https://km.sankuai.com/page/2729091498 |
| KNB.logout → MSI.mtLogout | https://km.sankuai.com/page/2728724580 |
| KNB.openAppSetting → MSI.openSetting | https://km.sankuai.com/page/2729061843 |
| KNB.openMiniProgram → MSI.openWxMiniProgram | https://km.sankuai.com/page/2728564971 |
| KNB.openPageForResult → MSI.openLink | https://km.sankuai.com/page/2728575188 |
| KNB.openPage → MSI.openPage | https://km.sankuai.com/page/2728912671 |
| KNB.openScheme → MRNUtils.openUrl | https://km.sankuai.com/page/2728933764 |
| KNB.openWebview → MSI.openPage | https://km.sankuai.com/page/2729180846 |
| KNB.pickCity → MSI.pickCity | https://km.sankuai.com/page/2728465552 |
| KNB.pickContact → MSI.chooseContact | https://km.sankuai.com/page/2728604820 |
| KNB.playVideo → MSI.playVideo | https://km.sankuai.com/page/2728495130 |
| KNB.previewImage → MSI.previewImage | https://km.sankuai.com/page/2728992412 |
| KNB.publish → MSI.publish | https://km.sankuai.com/page/2729131136 |
| KNB.requestPermission → MSI.checkPermission、authorize | https://km.sankuai.com/page/2729230502 |
| KNB.scanQRCode → MSI.scanCode | https://km.sankuai.com/page/2729210841 |
| KNB.sendLog → MSI.loganWrite | https://km.sankuai.com/page/2729161324 |
| KNB.sendSMS → MSI.sendSms | https://km.sankuai.com/page/2728932703 |
| KNB.sendSnifferLog → MSI.sendBabelLog | https://km.sankuai.com/page/2728922525 |
| KNB.setBackgroundColor → MSI.setBackgroundColor | https://km.sankuai.com/page/2728882614 |
| KNB.setBouncesEnabled → MSI.setBouncesEnabled | https://km.sankuai.com/page/2728544917 |
| KNB.setBrightness → MSI.setScreenBrightness | https://km.sankuai.com/page/2728962550 |
| KNB.setClipboard → MSI.setClipboardData | https://km.sankuai.com/page/2728724712 |
| KNB.setLLButton → MSI.setLLButton | https://km.sankuai.com/page/2728734574 |
| KNB.setLRButton → MSI.setLRButton | https://km.sankuai.com/page/2729300295 |
| KNB.setNavButtons → MSI.setLLButton、setLRButton、setRLButton、setRRButton | https://km.sankuai.com/page/2729240789 |
| KNB.setNavigationBarHidden → MSI.setNavigationBarHidden | https://km.sankuai.com/page/2728773361 |
| KNB.setNavigationBar → MSI.setNavigationBar | https://km.sankuai.com/page/2728862922 |
| KNB.setResult → MSI.setPageResult | https://km.sankuai.com/page/2729031876 |
| KNB.setRRButton → MSI.setRRButton | https://km.sankuai.com/page/2729250531 |
| KNB.setStatusBarStyle → MSI.setStatusBarStyle | https://km.sankuai.com/page/2729141690 |
| KNB.setStorage → MSI.setSharedStorage | https://km.sankuai.com/page/2729081491 |
| KNB.setupEvent → MSI.addPhoneCalendar | https://km.sankuai.com/page/2728545089 |
| KNB.shareImage → MSI.mtShare | https://km.sankuai.com/page/2728823240 |
| KNB.shareMiniProgram → MSI.mtShare | https://km.sankuai.com/page/2728614970 |
| KNB.share → MSI.mtShare | https://km.sankuai.com/page/2728455956 |
| KNB.showKeyboard → MSI.showKeyboard | https://km.sankuai.com/page/2728714720 |
| KNB.startRecord → MSI.RecorderManager.start | https://km.sankuai.com/page/2729091655 |
| KNB.stopLocating → MSI.stopLocationUpdate | https://km.sankuai.com/page/2729250553 |
| KNB.stopRecord → MSI.RecorderManager.stop | https://km.sankuai.com/page/2728764113 |
| KNB.subscribe → MSI.subscribeForSubId | https://km.sankuai.com/page/2728585116 |
| KNB.toast → MSI.showToast | https://km.sankuai.com/page/2729250557 |
| KNB.unsubscribe → MSI.unsubscribeWithSubId | https://km.sankuai.com/page/2729191186 |
| KNB.uploadFile → MSI.uploadFile | https://km.sankuai.com/page/2728654856 |
| KNB.uploadImage → MSI.uploadFile | https://km.sankuai.com/page/2728545115 |
| KNB.uploadLog → MSI.loganUpload | https://km.sankuai.com/page/2728545118 |
| KNB.uploadMedia → MSI.uploadFile | https://km.sankuai.com/page/2729161505 |
| KNB.vibrate → MSI.vibrateShort、vibrateLong | https://km.sankuai.com/page/2728962583 |
| KNB.setRLButton → MSI.setRLButton | https://km.sankuai.com/page/2728614954 |

## 文档访问说明

- **文档内容**：用 agent-browser snapshot 获取的是当前页完整 DOM 快照，正文（标题、入参/出参表格、示例代码、迁移注意事项）与 KM 页面一致；表格在快照里以结构化 table/cell/row 形式出现，可直接用于「对照文档」与合规检查。
- **阅读 snapshot 时**：正文多数从第一个 `heading "KNB xxx 到 MSI xxx 映射关系文档"` 开始，以该正文区的 heading/paragraph/table/list/code 为准。
