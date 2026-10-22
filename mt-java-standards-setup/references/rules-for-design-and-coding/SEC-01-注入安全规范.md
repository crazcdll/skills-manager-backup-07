---
ruleType: Model Request
description: 写SQL拼接/HTTP接口/Cookie/表单提交时读我。防SQL注入、HTTP安全头与Cookie安全、CSRF防护。出现SQL拼接或处理HTTP请求时必读。
category: 安全规范
priority: high
---

# SEC-01：注入安全规范

## 一、说明

本规范定义了「注入类」攻击面的防御标准，包括 SQL 注入、HTTP 安全头与 Cookie 安全、CSRF 跨站请求伪造等。

**数据类安全话题**（XSS 与脱敏、Token 安全传递、加解密算法、反序列化）请参见 `SEC-02-数据保护规范.md`；**文件操作安全与 SSRF**请参见 `SEC-03-访问控制与网络安全规范.md`；**认证与越权**请参见 `HA-12-安全编码规范.md`。

## 二、规则内容

### SEC-A003 [强制] SQL 注入防护

对于动态 SQL 场景（表名、列名、ORDER BY 等），必须实施白名单校验或使用安全 SDK。

**说明**：
- **首选**：使用 MyBatis 的 `#{}` 参数化绑定（预编译）
- **`${}` 仅可在动态表名/列名场景使用**，且必须白名单校验
- ORDER BY / GROUP BY 动态字段名需通过 `SecSdk.isValidSqlIdentifier()` 校验
- 安全 SDK 依赖：`com.sankuai.security:sec-sdk:1.3.15`
- 完整 ORM 规范详见 `DB-01` ORM002；SQL 开发规范详见 `DB-02` N015

##### good case:

```java
// ${} + SecSdk 校验（动态列名场景）
if (SecSdk.isValidSqlIdentifier(columnName) && SecSdk.isValidSqlIdentifier(order)) {
    String sql = "SELECT id, name FROM user_table ORDER BY " + columnName + " " + order;
}
```

```xml
<!-- #{} 参数化绑定（推荐） -->
<select id="findByStatus" resultType="User">
    SELECT id, name FROM user_table WHERE status = #{status}
</select>
```

##### bad case:

```java
// 直接拼接用户输入 — SQL 注入！
String sql = "SELECT * FROM user_table WHERE name = '" + userName + "'";
// ${} 无校验 — SQL 注入！
String sql = "SELECT * FROM user_table ORDER BY " + request.getParameter("sort");
```

### SEC-A004 [强制] HTTP 安全头与 Cookie 安全

敏感 Cookie 必须设置 HttpOnly、Secure 和 SameSite 属性。HTTP 响应头必须包含安全头防止点击劫持和 MIME 嗅探。

**说明**：
- Cookie 设置：`HttpOnly=true`（防 XSS 窃取）、`Secure=true`（仅 HTTPS）、`SameSite=Strict/Lax`
- 必须设置的响应头：
  - `X-Content-Type-Options: nosniff`
  - `X-Frame-Options: DENY`（防点击劫持）
  - `Content-Security-Policy: default-src 'self'`

##### good case:

```java
ResponseCookie cookie = ResponseCookie.from("sid", sessionId)
    .httpOnly(true)
    .secure(true)
    .sameSite("Strict")
    .build();

response.setHeader(HttpHeaders.SET_COOKIE, cookie.toString());
response.setHeader("X-Content-Type-Options", "nosniff");
response.setHeader("X-Frame-Options", "DENY");
response.setHeader("Content-Security-Policy", "default-src 'self'");
```

##### bad case:

```java
// 不安全的 Cookie
response.addCookie(new Cookie("sid", sessionId));  // 无 HttpOnly/Secure/SameSite
// 缺少安全响应头
```

### SEC-A006 [强制] CSRF 防护

涉及状态改变的请求（POST/PUT/DELETE）必须实施 CSRF 防护机制。

**说明**：
- 同站请求（SameSite Cookie）：设置 `SameSite=Strict` 或 `Lax`（已在 SEC-A004 覆盖）
- Token 模式：每个会话生成唯一 CSRF Token，状态改变请求必须携带并校验
- Origin/Referer 校验：服务端验证请求来源是否为允许的域名
- 认证与授权基础详见 `HA-12` HA-SEC001~HA-SEC002

##### good case:

```java
// SameSite Cookie（最简方案，已在 SEC-A004 配置）
// 或 Token 模式：
@PostMapping("/api/order")
public Result createOrder(@RequestHeader("X-CSRF-Token") String csrfToken,
                         @RequestBody OrderRequest request,
                         HttpSession session) {
    String sessionToken = (String) session.getAttribute("CSRF_TOKEN");
    if (!Objects.equals(csrfToken, sessionToken)) {
        return Result.forbidden("CSRF token mismatch");
    }
    return orderService.createOrder(request);
}
```

##### bad case:

```java
// 无任何 CSRF 防护 — 跨站请求可伪造！
@PostMapping("/api/order")
public Result createOrder(@RequestBody OrderRequest request) {
    return orderService.createOrder(request);  // 攻击站点可诱导用户触发
}
```

## 三、规范执行要点

- ✗ 禁止 `${}` 无校验拼接 SQL
- ✗ 禁止 Cookie 不设 HttpOnly/Secure/SameSite
- ✗ 禁止缺少 X-Content-Type-Options / X-Frame-Options / CSP
- ✗ 禁止状态改变接口无 CSRF 防护
