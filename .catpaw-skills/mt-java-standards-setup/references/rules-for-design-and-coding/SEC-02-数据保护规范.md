---
ruleType: Model Request
description: 代码涉及日志输出/外部内容透传(通知/消息体)/用户输入入库/反序列化时读我。强制XSS防御(SecSdk.encodeForHTML)、敏感信息脱敏(身份证/手机/银行卡,脱敏规则唯一正本)、反序列化白名单(ObjectInputFilter/禁Default Typing/优先JSON)。remark或用户输入透传外部时必读。
category: 安全规范
priority: high
---

# SEC-02：数据保护规范

## 一、说明

本规范定义了**数据内容安全**的防御标准，包括 XSS 与脱敏和反序列化两个领域。

**文件操作安全（路径遍历）与网络访问安全（SSRF）详见 `SEC-03-访问控制与网络安全规范.md`。**

**认证授权与越权防护详见 `HA-12-安全编码规范.md`。**

**注入类安全（OS命令/XXE/SQL注入/Cookie/重定向/CSRF）详见 `SEC-01-注入安全规范.md`。**

## 二、规则内容

以下示例仅用于说明规则边界与意图，不代表唯一实现方式；实际生成或审查代码时，应优先复用项目现有框架、工具类、SDK 与命名，并以是否满足规则约束为判断标准。

### SEC-B001 [强制] XSS 防御与敏感信息脱敏

所有来自用户的输入在输出到前端页面前必须进行 XSS 转义处理。个人敏感信息必须脱敏展示。

#### XSS 转义

根据输出上下文选择转义函数：

| 上下文 | 函数 |
|--------|------|
| HTML 内容 | `SecSdk.encodeForHTML(name)` |
| JavaScript | `SecSdk.encodeForJavaScript(callback)` |
| URL 属性 | `SecSdk.encodeForURL(url)` |
| 富文本 | `SecSdk.getCleanHTML(content)` |

#### 敏感信息脱敏

| 信息类型 | 脱敏规则 | 示例 |
|----------|---------|------|
| 鉴权信息（口令/密保） | 不允许展示 | — |
| 身份证号 | 仅显示首尾字符 | `3****************1` |
| 手机号码 | 隐藏中间6位 | `138******78` |
| 地址 | 最多到"区"级 | 北京市朝阳区*** |
| 银行卡号 | 仅显示最后4位 | `************8639` |

##### good case:

```java
// HTML 上下文转义
String safeName = SecSdk.encodeForHTML(name);
return "<div>用户名：" + safeName + "</div>";

// 富文本净化
String cleanContent = SecSdk.getCleanHTML(content);
```

##### bad case:

```java
// 直接输出用户输入 — XSS 漏洞！
return "<div>用户名：" + name + "</div>";  // name 可为 <script>alert(1)</script>
```

---

### SEC-B004 [强制] 反序列化安全

禁止对不受信任的数据进行反序列化。推荐使用 JSON 等文本协议替代 Java 原生序列化。

**说明**：
- 必须使用 `ObjectInputFilter` 或白名单限制可反序列化的类
- 优先使用 JSON（Jackson/Fastjson）替代 Java 原生 `ObjectInputStream`
- 反序列化后的对象必须进行完整性和有效性校验（validate）
- 禁止 Jackson 开启 Default Typing（`enableDefaultTyping()`）

##### good case:

```java
// ObjectInputFilter 白名单
ObjectInputFilter filter = ObjectInputFilter.Config.createFilter(
    "com.meituan.dto.*;!*"
);
ObjectInputStream inputStream = new ObjectInputStream(source);
inputStream.setObjectInputFilter(filter);
Object obj = inputStream.readObject();
validate(obj);  // 完整性校验

// 推荐：JSON 替代原生序列化
String json = objectMapper.writeValueAsString(data);
Data result = objectMapper.readValue(json, Data.class);
```

##### bad case:

```java
// 无任何防护 — 反序列化漏洞！
ObjectInputStream inputStream = new ObjectInputStream(source);
Object obj = inputStream.readObject();  // 可执行任意代码
return obj;
```

---

## 三、规范执行要点

### 代码审查检查点
- [ ] 用户输入输出前是否做了 XSS 转义
- [ ] 敏感信息展示是否做了脱敏处理
- [ ] 反序列化是否有 ObjectInputFilter 或白名单
- [ ] 是否优先使用 JSON 替代原生序列化
