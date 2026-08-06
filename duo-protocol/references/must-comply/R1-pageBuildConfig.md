# 2、页面静态配置 pageBuildConfig.json

[示例文档](../../examples/duo-page-demo/pageBuildConfig.json)

## 目录

- [一、PageBuildConfig 结构](#一pagebuildconfig-结构) — baseUrl/pageUrl/pageQuery/commonParams 接口定义
- [二、字段说明](#二字段说明) — baseUrl、pageUrl、pageQuery
- [三、commonParams 公共参数配置](#三commonparams-公共参数配置) — location/userInfo/city/storage/pnConfig/customParams
- [四、完整示例](#四完整示例) — 酒店提单页面配置完整 JSON
- [五、与 1.0 版本差异](#五与-10-版本差异)
- [六、注意事项](#六注意事项)
- [七、示例](#七示例)

## 一、PageBuildConfig 结构

```typescript
interface PageBuildConfig {
  // 请求的 API 地址前缀。只有前端关心，后端不需要解析
  baseUrl: string;
  // 发布页面的地址。只有前端关心，后端不需要解析
  pageUrl: { mrn?: string; h5?: string };
  // 前后端引擎都不需要解析，只做配置约束
  pageQuery: {
    [key: string]: { required: boolean }
  };
  // 前端需要解析，页面编译时导入
  commonParams: PageBuildConfigCommonParams;
}
```

## 二、字段说明

### 2.1 baseUrl

请求的 API 地址前缀，只有前端关心，后端不需要解析。

```json
{
  "baseUrl": "https://ticket.meituan.com/ticket/order/preview"
}
```

### 2.2 pageUrl

发布页面的地址，只有前端关心，后端不需要解析。

```json
{
  "pageUrl": {
    "mrn": "rn_meishi_ticket-submit&main",
    "h5": "ticket-submit"
  }
}
```

### 2.3 pageQuery

页面查询参数配置，前后端引擎都不需要解析，只做配置约束。

```json
{
  "pageQuery": {
    "dealId": {
      "required": true
    },
    "activityId": {
      "required": false
    }
  }
}
```

## 三、commonParams 公共参数配置

```typescript
interface PageBuildConfigCommonParams {
  // 是否开启预请求
  usePn?: boolean;
  // 预请求配置
  pnConfig?: PNConfig;
  // regionId 通参配置
  regionId?: RegionIdConfig;
  // 经纬度配置
  location?: LocationConfig;
  // 用户信息配置
  userInfo?: UserInfoConfig;
  // 城市信息配置
  city?: CityConfig;
  // 环境信息配置
  systemInfo?: {};
  // fingerprint 配置
  fingerprint?: {};
  // KNB storage 配置
  storage?: StorageConfig;
  // 自定义参数配置。不建议使用，因为不支持预请求
  customParams?: CustomParams;
}
```

### 3.1 location 经纬度配置

```typescript
interface LocationConfig {
  // 定位类型
  type?: 'GCJ02' | 'WGS84';
  // 定位需要场景 token。useSync=false 时必填
  sceneToken?: string;
  // 使用同步桥。是缓存定位，速度更快，但是不满足某些获取实时定位的产品诉求
  useSync?: boolean;
  // 是否优先使用跳链参数。默认 true，速度更快，但是不满足某些获取实时定位的产品诉求
  useQuery?: boolean;
  // 是否获取精度等。与 useQuery 互斥
  useAll?: boolean;
}
```

### 3.2 userInfo 用户信息配置

```typescript
interface UserInfoConfig {
  // 是否强制登录，默认 true
  forceLogin?: boolean;
  // 是否优先使用跳链参数。默认 true，速度更快。与 forceLogin 互斥
  useQuery?: boolean;
  // 使用同步桥获取用户信息。默认 false
  useSync?: boolean;
}
```

### 3.3 city 城市信息配置

```typescript
interface CityConfig {
  // 使用同步桥。默认 true，速度更快，但是无法获取到定位程序
  useSync?: boolean;
  // 是否优先使用跳链参数。默认 true，速度更快，但是无法获取到定位城市
  useQuery?: boolean;
  // 是否获取定位城市 locCityId。与 useSync、useQuery 互斥
  useAll?: boolean;
}
```

### 3.4 storage 存储配置

```typescript
interface StorageConfig {
  /**
   * @desc 缓存信息；缓存(MRN端为KNB)
   * @triggers 缓存、storage、接口请求参数
   * @example {
   *    selectedLinkedTask: {
   *      "storageKey": "_continuousOrderTaskCheckStatus_"
   *    }
   * }
   * 出码后的 JS 伪代码（仅仅作为学习了解、只需要按照上面的格式生成协议即可）
      COMMON_PARAMS.storage.selectedLinkedTask = await KNB.getStorage({
        key: "_continuousOrderTaskCheckStatus_",
      })
  */
  [key: string]: {
    storageKey: string;
  };
}
```

### 3.5 预请求配置

```typescript
interface PNConfig {
  // 预请求配置条件
  condition?: string;
}

interface RegionIdConfig {
  // 是否开启 regionId 通参注入
  enable?: boolean;
}
```

### 3.6 customParams 自定义参数

```typescript
interface CustomParams {
  [key: string]: {  // 入参的 key
    args?: string;  // 函数执行所需要的参数
    content: NPMInfo;  // 函数的 npm 信息
  }
}

interface NPMInfo {
  package: string;
  version: string;
  destructuring: boolean;
  exportName: string;
  library?: string;
  url?: string;
}
```

## 四、完整示例
```js
{
  "baseUrl": "https://apihotel.meituan.com/hotelorder/trade/precreate",
  "pageUrl": {
    "mrn": "rn_hotel_hotelchannel-orderfill-duo&main",
    "h5": "hotelchannel-orderfill-duo"
  },
  "pageQuery": {
    "goods_id,goodsId": {
      "required": true,
      "pnMatch": true
    },
    "checkinDate,checkindate,checkin,checkInDate": {
      "required": false,
      "pnMatch": true
    },
    "checkoutDate,checkoutdate,checkout,checkOutDate": {
      "required": false,
      "pnMatch": true
    },
    "adult_num,adultNum,adultnum,adultCount,roomDefaultAdult": {
      "required": false,
      "pnMatch": true
    },
    "child_age,childrenAge": {
      "required": false,
      "pnMatch": true
    },
    "room_num": {
      "required": false,
      "pnMatch": true
    }
  },
  "commonParams": {
    "usePn": true,
    "systemInfo": {},
    "location": {
      "type": "GCJ02",
      "sceneToken": "dd-f6b6963e1a98f385",
      "useSync": true,
      "useQuery": false,
      "useAll": true
    },
    "userInfo": {
      "forceLogin": true,
      "useQuery": false,
      "useSync": true
    },
    "city": {
      "useSync": false,
      "useQuery": false,
      "useAll": true
    },
    "fingerprint": {},
    "fontConfig": {
      "fontFamily": [
        "MTNewDigitalDisplay"
      ]
    },
    "regionId": {
      "enable": true
    },
    "h5guard": {
      "enabled": true,
      "geo": false
    },
    "modulesLoadConfig": {
      "lazyModules": {
        "723": {
          "enabled": true
        },
      },
      "useRAMBundle": true
    },
    "storage": {
      "distributionUnpl": {
        "storageKey": "unpl"
      },
      "selectedLinkedTask": {
        "storageKey": "_continuousOrderTaskCheckStatus_"
      }
    },
    "elinkInfo": {
      "elinkDocId": ""
    },
    "leez": {
      "remEnabled": true
    },
    "customHttpConfig": {
      "items": [
        {
          "key": "bizType",
          "type": "params",
          "valueExpression": "COMMON_PARAMS.isSubmit ? '-1' : (PAGE_QUERY.biz_type || (PAGE_QUERY.oh_room_price_total ? '2' : '1'))"
        }
      ],
      "mrnChannel": "hotel"
    }
  }
}

```

## 五、与 1.0 版本差异

- 新增 `dependencies`：npm 包列表
- 移除 `dynamicDataConfig.currentState`：全局状态
- 新增 `constData`：用于定义常量，在视图树中使用（入参配置中不可使用常量）
- `events` 改名为 `logics`

## 六、注意事项

1. **baseUrl**：只有前端关心，后端不需要解析
2. **pageUrl**：只有前端关心，后端不需要解析
3. **pageQuery**：前后端引擎都不需要解析，只做配置约束
4. **commonParams**：前端需要解析，页面编译时导入
5. **customParams**：不建议使用，因为不支持预请求

## 七、示例

[酒店提单页面配置示例](../../examples/duo-page-demo/pageBuildConfig.json)

## 参考文档

https://km.sankuai.com/collabpage/1749282893
