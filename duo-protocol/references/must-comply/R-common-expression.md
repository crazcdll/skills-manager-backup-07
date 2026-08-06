# DUO 表达式配置

## 依赖 skill

- 安装`groovy-syntax`: `mtskills i groovy-syntax`
- 在创建、修改和校验 groovy 文件时、一定要使用该 skill 作为参考

## 定义

- **组件入参**：指的是前端组件使用的 props
- **接口入参**：指的是后端 HTTP 请求的参数

## 一、字段类型

表达式支持以下类型：

| 类型    | 说明          |
| ------- | ------------- |
| Number  | 数字类型      |
| String  | 字符串类型    |
| Boolean | 布尔类型      |
| Object  | 对象类型      |
| List    | 列表/数组类型 |

> 部分样式字段类型未明确，此时需要主动选择对应类型。

## 二、表达式中的变量

### 2.1 基础变量

| 变量名           | 含义             | 应用场景              | 说明                                                                                                          |
| ---------------- | ---------------- | --------------------- | ------------------------------------------------------------------------------------------------------------- |
| `PAGE_QUERY`     | 页面参数         | 无特殊要求            | 用于获取页面跳链中的参数                                                                                      |
| `COMMON_PARAMS`  | 公共参数         | 无特殊要求            | 用于获取系统信息，如位置信息、用户信息、系统信息、指纹。需要在配置平台勾选这些信息                            |
| `SYSTEM_INFO`    | 公共参数（后端） | 后端使用              | 可以获取到系统信息，如 realRemoteIp、user-agent、utm 参数等                                                   |
| `DATA_SOURCE`    | 数据源出参       | 一般组件 Props 都使用 | 数据源的返回结果。**在数据源入参中不可以使用 DATA_SOURCE 变量**                                               |
| `CONST`          | 常量             | 可复用表达式使用      | 如果同一个表达式会多次使用，可以将其定义为常量。**CONST 之间不可以互相引用，常量配置中不可以使用 CONST 变量** |
| `PREV_DATA`      | 上次数据源结果   | 接口入参使用          | 使用上一次接口返回的数据。**只能在入参配置中使用**                                                            |
| `NODE.xxx.props` | 节点属性         | 接口入参使用          | 模块上保存的状态数据。**建议只能在入参配置中使用**                                                            |
| `PROPS`          | 节点属性         | 双向绑定使用          | 使用 PROPS 可以获取到自身节点的属性                                                                           |

### 2.2 COMMON_PARAMS 类型定义

```typescript
interface CommonParams {
  // 是否为 preview 请求
  isPreview?: boolean | '' | 'true';
  // 是否为 update 请求
  isUpdate?: boolean | '' | 'true';
  // 是否为 submit 请求
  isSubmit?: boolean | '' | 'true';
  location?: {
    lat?: number;      // 经度
    lng?: number;      // 纬度
    accuracy?: number; // 精度（需开启配置）
  };
  userInfo?: {
    userId?: string;
    token?: string;
    dpid?: string;     // 点评 App 内使用
    uuid?: string;     // (废弃) 取值逻辑不统一，不建议使用
    openId?: string;   // 小程序及其 webview 环境有
    uuidV2?: string;   // 2025.04.25 新增
    mtuuid?: string;   // 2025.04.25 新增
  };
  cityInfo?: {
    cityId?: string;    // 首页选择城市
    locCityId?: string; // 定位城市（仅 MRN 端）
  };
  systemInfo?: {
    version?: string;        // APP 版本
    systemVersion?: string;  // 系统版本
    device?: string;         // 设备信息
    platform?: string;       // 端：ios/android
    IS_MT?: boolean;         // 是否为美团
    IS_DP?: boolean;         // 是否为点评
    IS_TICKET?: boolean;     // 是否为门票
    isMRN?: boolean;         // 是否是 MRN
    isWeb?: boolean;         // 是否是 WEB
    isWeChatMiniProgram?: boolean;
    mpAppId?: string;        // 小程序唯一标识
    mpAppVersion?: string;   // 小程序主包版本号
    mpPluginAppId?: string;  // 小程序插件版本
    isDebug?: boolean;
    envInWeb: {
      isWebInApp?: boolean;
      isWebInMtApp?: boolean;
      isWebInDpApp?: boolean;
      isWebInWeChatMiniProgram?: boolean;
      isWebInTicketWeChatMiniProgram?: boolean;
      // ...更多小程序环境判断
    };
  };
  fingerprint?: {
    fingerprint?: string;
  };
  /**
   * @desc 缓存信息；缓存(MRN端为KNB)
   * @triggers 缓存、storage、接口请求参数
   * @example { // selectedLinkedTask 作为 key、_continuousOrderTaskCheckStatus_ 作为 key 值
   *    selectedLinkedTask: {
   *      "storageKey": "_continuousOrderTaskCheckStatus_"
   *    }
   * }
  */
  storage?: {
    [key: string]: string | undefined;
  };
}
```

### 2.3 SYSTEM_INFO 类型定义

```typescript
interface SystemInfo {
  realRemoteIp?: string;
  'x-real-ip'?: string;
  'user-agent'?: string;
  utm_term?: string;
  utm_campaign?: string;
  utm_medium?: string;
  utm_source?: string;
  utm_content?: string;
}
```

### 2.4 关于 uuid 和 dpid

- **点评 App 内**：如果期望用 dpid，可以使用 `userInfo.dpid`
- **userInfo.uuid**：在不同情况下取值逻辑不统一，不建议使用
- **uuidV2**：不考虑低版本 bundle 兼容性时使用；考虑兼容性需要取 `IS_DP ? dpid : uuid`

## 三、高阶用法

| 变量名    | 含义            | 应用场景                     | 说明                                                                   |
| --------- | --------------- | ---------------------------- | ---------------------------------------------------------------------- |
| `PAYLOAD` | update 携带数据 | 在触发 update 时配置携带数据 | 只在当次 update 生效，多次 update 无法复用。**建议只在入参配置中使用** |

### PAYLOAD 使用场景

只适用于需要后端校验的 update 场景。例如：选中某个券，前端不立即更新选中状态，而是调用 update，将需要选中的券通过 PAYLOAD 传给业务后端，业务后端判断是否可以选中这个券，前端再更新状态。

## 四、不常用变量

| 变量名             | 含义              | 应用场景              | 说明                                                                                        |
| ------------------ | ----------------- | --------------------- | ------------------------------------------------------------------------------------------- |
| `FOR.index`        | 循环项下标        | 循环渲染内使用        | 必须在循环渲染内使用                                                                        |
| `FOR.item`         | 循环项值          | 循环渲染内使用        | 必须在循环渲染内使用                                                                        |
| `UPDATE.xxx.props` | update 更新的字段 | 判断 props 是否被修改 | `UPDATE.module1.props.prop1=true` 表示本次 update 时，module1 的 prop1 是否被双向绑定更新了 |

## 五、常见表达式示例

### 5.1 获取页面参数

```groovy
string('dealId') {{ PAGE_QUERY?.dealId ?: '' }}
string('activityId') {{ PAGE_QUERY?.activityId ?: '' }}
```

### 5.2 获取用户信息

```groovy
string('userId') {{ COMMON_PARAMS.userInfo?.userId ?: '' }}
string('token') {{ COMMON_PARAMS.userInfo?.token ?: '' }}
```

### 5.3 获取数据源数据

```groovy
string('title') {{ DATA_SOURCE?.data?.dealInfo?.title ?: '' }}
string('imageUrl') {{ DATA_SOURCE?.data?.dealInfo?.imageUrl ?: '' }}
number('price') {{ DATA_SOURCE?.data?.dealInfo?.price ?: 0 }}
```

### 5.4 使用常量

在 `constData.groovy` 中定义：

```groovy
constant {
  string('pageTitle') {{ '门票提单' }}
  number('childPrice') {{ DATA_SOURCE?.data?.dealInfo?.childPrice ?: 40 }}
  number('adultPrice') {{ DATA_SOURCE?.data?.dealInfo?.adultPrice ?: 90 }}
}
```

在 `struct.groovy` 中使用：

```groovy
string('text') {{ CONST.pageTitle }}
number('price') {{ CONST.childPrice }}
```

### 5.5 条件表达式

三元运算：

```groovy
string('status') {{ DATA_SOURCE?.data?.status == 1 ? '已支付' : '未支付' }}
```

兜底运算符：

```groovy
string('name') {{ DATA_SOURCE?.data?.userName ?: '游客' }}
```

安全访问：

```groovy
string('value') {{ DATA_SOURCE?.data?.nested?.value ?: '' }}
```

### 5.6 环境判断

判断是否为美团 App：

```groovy
bool('isMT') {{ COMMON_PARAMS.systemInfo?.IS_MT ?: false }}
```

判断是否为 MRN：

```groovy
bool('isMRN') {{ COMMON_PARAMS.systemInfo?.isMRN ?: false }}
```

判断是否为 Web：

```groovy
bool('isWeb') {{ COMMON_PARAMS.systemInfo?.isWeb ?: false }}
```

## 六、注意事项

1. **DATA_SOURCE 限制**：在数据源入参中不可以使用 `DATA_SOURCE` 变量，可以使用 `PREV_DATA`。

2. **CONST 限制**：CONST 之间不可以互相引用，常量配置中不可以使用 CONST 变量。

3. **PREV_DATA 限制**：只能在入参配置中使用。

4. **NODE.xxx.props 限制**：建议只在入参配置中使用，组件 props 入参场景不可以使用。

5. **Boolean 类型注意**：点评 Android 端预请求会把配置的 `true` 转为 `'true'`，此时 `'true'` 表示真，`undefined` 或 `''` 表示假。

6. **systemInfo.isDebug**：值不准确，建议让后端返回对应字段区分接口环境。

7. **安全访问**：使用 `?.` 安全访问操作符避免空指针异常，注意链式安全访问每级都要加 `?.`。

## 参考文档

https://km.sankuai.com/collabpage/1733888444
