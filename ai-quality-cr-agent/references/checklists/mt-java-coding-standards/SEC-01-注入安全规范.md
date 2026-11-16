---
ruleType: Model Request
description: 注入类安全规范，涵盖OS命令注入防护、XML XXE攻击防护、SQL注入防护、HTTP安全头与Cookie安全、URL重定向白名单、CSRF防护等6项注入攻击面防御规则
category: 安全规范
priority: high
---

# SEC-01：注入安全规范

## 一、说明

本规范定义了所有「注入类」攻击面的防御标准，包括 OS 命令注入、XML 外部实体(XXE)注入、SQL 注入、URL 重定向开放重定向、CSRF 跨站请求伪造等。

**数据类安全话题**（XSS 与脱敏、Token 安全传递、加解密算法、反序列化）请参见 `SEC-02-数据保护规范.md`；**文件操作安全与 SSRF**请参见 `SEC-03-访问控制与网络安全规范.md`；**认证与越权**请参见 `HA-12-安全编码规范.md`。

## 二、规则内容

### java-l1:SEC-01.SEC-A001 [强制] OS 命令注入防护

禁止将用户可控的参数直接拼接到系统命令中执行。如必须使用 OS 命令，参数需严格白名单校验，禁止使用命令连接符。

**说明**：
- 优先使用 `ProcessBuilder` 替代 `Runtime.exec()`
- 参数列表方式传参（避免 shell 解析）
- 白名单校验业务类型/文件名等用户输入
- 禁止使用 `;` `|` `&&` 等命令连接符

##### good case:

```java
public Process listLogFiles(String bizType) throws IOException {
    if (!ALLOWED_BIZ_TYPES.contains(bizType)) {
        throw new IllegalArgumentException("invalid biz type");
    }
    // ProcessBuilder 参数列表传参，避免 shell 拼接
    return new ProcessBuilder("ls", "/data/log/" + bizType).start();
}
```

##### bad case:

```java
// 直接拼接用户输入 — OS 命令注入！
public Process listLogFiles(String bizType) throws IOException {
    return Runtime.getRuntime().exec("ls /data/log/" + bizType);
}
```

### java-l1:SEC-01.SEC-A002 [强制] XML XXE 攻击防护

解析 XML 时必须禁用外部实体和 DTD，防止 XXE（XML External Entity）攻击导致任意文件读取或 SSRF。

**说明**：
- `DocumentBuilderFactory` / `SAXParserFactory` 必须配置安全特性
- 必须设置 `disallow-doctype-decl = true`
- 必须禁用 `external-general-entities` 和 `external-parameter-entities`
- 必须设置 `setExpandEntityReferences(false)`

##### good case:

```java
DocumentBuilderFactory factory = DocumentBuilderFactory.newInstance();
factory.setFeature("http://apache.org/xml/features/disallow-doctype-decl", true);
factory.setFeature("http://xml.org/sax/features/external-general-entities", false);
factory.setFeature("http://xml.org/sax/features/external-parameter-entities", false);
factory.setExpandEntityReferences(false);
DocumentBuilder builder = factory.newDocumentBuilder();
Document document = builder.parse(inputStream);
```

##### bad case:

```java
// 默认配置 — 存在 XXE 漏洞！
DocumentBuilderFactory factory = DocumentBuilderFactory.newInstance();
DocumentBuilder builder = factory.newDocumentBuilder();
Document document = builder.parse(inputStream);  // 可被利用读取 /etc/passwd
```

### java-l1:SEC-01.SEC-A003 [强制] SQL 注入防护

对于动态 SQL 场景（表名、列名、ORDER BY 等），必须实施白名单校验或使用安全 SDK。

**说明**：
- **首选**：使用 MyBatis 的 `#{}` 参数化绑定（预编译）
- **`${}` 仅可在动态表名/列名场景使用**，且必须白名单校验
- ORDER BY / GROUP BY 动态字段名需通过 `SecSdk.isValidSqlIdentifier()` 校验
- 安全 SDK 依赖：`com.sankuai.security:sec-sdk:1.3.15`
- 完整 ORM 规范详见 `DB-01` java-l1:DB-01.ORM002；SQL 开发规范详见 `DB-02` java-l1:DB-02.N015

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

### java-l1:SEC-01.SEC-A004 [强制] HTTP 安全头与 Cookie 安全

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

### java-l1:SEC-01.SEC-A005 [强制] URL 重定向白名单

禁止未验证的 URL 重定向。重定向前必须对目标地址进行白名单校验，防止开放重定向攻击（钓鱼）。

**说明**：
- 重定向目标必须来自白名单域名列表
- 禁止直接使用用户输入的 URL 作为重定向目标
- 用户输入参数有效性验证参见 java-l1:SEC-01.SEC-A004 说明

##### good case:

```java
@GetMapping("/jump")
public void redirect(@RequestParam("target") String target, HttpServletResponse response) throws IOException {
    if (!ALLOWED_REDIRECT_HOSTS.contains(target)) {
        response.sendError(HttpServletResponse.SC_BAD_REQUEST);
        return;
    }
    response.sendRedirect(target);
}
```

##### bad case:

```java
// 未验证的重定向 — 开放重定向漏洞！
@GetMapping("/jump")
public void redirect(@RequestParam("target") String target, HttpServletResponse response)
    throws IOException {
    response.sendRedirect(target);  // 攻击者可构造 ?target=https://evil.com
}
```

### java-l1:SEC-01.SEC-A006 [强制] CSRF 防护

涉及状态改变的请求（POST/PUT/DELETE）必须实施 CSRF 防护机制。

**说明**：
- 同站请求（SameSite Cookie）：设置 `SameSite=Strict` 或 `Lax`（已在 java-l1:SEC-01.SEC-A004 覆盖）
- Token 模式：每个会话生成唯一 CSRF Token，状态改变请求必须携带并校验
- Origin/Referer 校验：服务端验证请求来源是否为允许的域名
- 认证与授权基础详见 `HA-12` java-l1:HA-12.HA-SEC001~java-l1:HA-12.HA-SEC002

##### good case:

```java
// SameSite Cookie（最简方案，已在 java-l1:SEC-01.SEC-A004 配置）
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

## 三、执行要求

1. 所有外部输入在进入命令解析器/SQL/XML/URL 重定向前必须校验
2. XML 解析器必须禁用外部实体
3. Cookie 必须设置 HttpOnly + Secure + SameSite
4. HTTP 响应头必须包含 X-Content-Type-Options + X-Frame-Options + CSP
5. URL 重定向必须白名单校验
6. 状态改变接口必须有 CSRF 防护

## 四、规范执行要点

### 核心要求
1. **OS命令**：禁止拼接用户输入，使用 ProcessBuilder + 白名单
2. **XXE**：禁用 DTD 和外部实体
3. **SQL注入**：#{} 参数化，${} 必须 SecSdk 校验
4. **Cookie/响应头**：HttpOnly + Secure + SameSite + 安全响应头
5. **重定向**：目标地址白名单校验
6. **CSRF**：SameSite Cookie 或 Token 校验

### 强制禁止
- ✗ 禁止将用户输入直接拼接到 OS 命令
- ✗ 禁止使用默认配置的 XML 解析器
- ✗ 禁止 `${}` 无校验拼接 SQL
- ✗ 禁止 Cookie 不设 HttpOnly/Secure/SameSite
- ✗ 禁止缺少 X-Content-Type-Options / X-Frame-Options / CSP
- ✗ 禁止未验证的 URL 重定向
- ✗ 禁止状态改变接口无 CSRF 防护

### 代码审查检查点
- [ ] 是否存在 `Runtime.exec()` 或 `ProcessBuilder` 直接拼接用户输入
- [ ] XML 解析器是否禁用了 DTD 和外部实体
- [ ] SQL 是否使用了 `#{}` 参数化绑定
- [ ] `${}` 使用处是否有 SecSdk 或白名单校验
- [ ] Cookie 是否设置了 HttpOnly + Secure + SameSite
- [ ] 响应头是否包含 X-Content-Type-Options + X-Frame-Options + CSP
- [ ] URL 重定向是否做了白名单校验
- [ ] POST/PUT/DELETE 接口是否有 CSRF 防护

