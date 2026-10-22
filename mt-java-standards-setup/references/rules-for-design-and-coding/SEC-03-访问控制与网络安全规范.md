---
ruleType: Model Request
description: 写文件上传下载/路径处理/外部HTTP调用/URL请求时读我。防路径遍历(toRealPath规范化/上传白名单/UUID重命名)、SSRF(内网IP白名单/DNS Rebinding防护/HTTPS),超时设置见HA-01。处理文件或发起外部请求时必读。
category: 安全规范
priority: high
---

# SEC-03：访问控制与网络安全规范

## 一、说明

本规范定义了**资源访问控制**类安全防御标准，包括文件操作安全（路径遍历攻击防护）和网络访问安全（SSRF 防护）两个领域。

**数据内容安全（XSS/脱敏/Token/加解密/反序列化）详见 `SEC-02-数据保护规范.md`。**

**认证授权与越权防护详见 `HA-12-安全编码规范.md`。**

**注入类安全（OS命令/XXE/SQL注入/Cookie/重定向/CSRF）详见 `SEC-01-注入安全规范.md`。**

## 二、规则内容

以下示例仅用于说明规则边界与意图，不代表唯一实现方式；实际生成或审查代码时，应优先复用项目现有框架、工具类、SDK 与命名，并以是否满足规则约束为判断标准。

### SEC-C001 [强制] 文件操作安全

文件路径来源于用户输入时必须进行路径遍历攻击防护。文件上传需校验类型和大小，使用白名单机制。

**说明**：
- 使用 `toRealPath()` / `canonicalPath()` 进行路径规范化
- 规范化后的路径必须以基础目录开头（防 `../` 路径遍历）
- 上传文件必须白名单校验 MIME 类型 + 限制大小
- 上传文件必须重命名存储（UUID），禁止使用原始文件名
- 临时文件使用后必须及时删除
- 上传目录禁止执行权限

##### good case:

```java
public Path saveFile(MultipartFile file, String bizDir) throws IOException {
    if (!ALLOWED_TYPES.contains(file.getContentType())) {
        throw new IllegalArgumentException("invalid file type");
    }
    if (file.getSize() > MAX_FILE_SIZE) {
        throw new IllegalArgumentException("file too large");
    }
    Path baseDir = Paths.get("/data/upload").toRealPath();
    // UUID 重命名 + normalize 防路径遍历
    Path target = baseDir.resolve(bizDir).resolve(UUID.randomUUID() + ".bin").normalize();
    if (!target.startsWith(baseDir)) {
        throw new SecurityException("path traversal attempt");
    }
    Files.copy(file.getInputStream(), target);
    return target;
}
```

##### bad case:

```java
// 直接使用用户输入的文件名 — 路径遍历！
File target = new File("/data/upload/" + fileName);
file.transferTo(target);  // fileName 可为 ../../etc/passwd
```

---

### SEC-C002 [强制] 网络访问安全与 SSRF 防护

目标地址来源于用户输入时必须进行白名单校验，禁止访问内网地址。所有外部网络请求必须设置超时。

**说明**：
- 用户传入的 URL 必须做白名单校验（防 SSRF）
- **禁止访问内网地址**：`10.*`、`172.16-31.*`、`192.168.*`、`127.*`、`169.254.*`
- 必须防范 DNS Rebinding 攻击（解析后二次验证 IP）
- 所有网络请求必须设置超时（connectTimeout + socketTimeout），超时设置的完整规范详见 `HA-01` HA-F001
- 涉及敏感数据传输必须使用 HTTPS

##### good case:

```java
public String query(String targetUrl) throws Exception {
    URL url = new URL(targetUrl);
    InetAddress addr = InetAddress.getByName(url.getHost());
    // SSRF 防护：解析后检查 IP 是否为内网
    if (isInternalIp(addr)) {
        throw new SecurityException("internal address not allowed");
    }
    RequestConfig config = RequestConfig.custom()
            .setConnectTimeout(3000)
            .setSocketTimeout(5000)
            .build();
    return Request.Get(targetUrl)
            .connectTimeout(config.getConnectTimeout())
            .socketTimeout(config.getSocketTimeout())
            .execute().returnContent().asString();
}

// 内网 IP 检测
private boolean isInternalIp(InetAddress addr) {
    byte[] ip = addr.getAddress();
    return addr.isLoopbackAddress() || addr.isSiteLocalAddress() || addr.isLinkLocalAddress();
}
```

##### bad case:

```java
// 无任何校验 — SSRF 漏洞！可探测内网服务
public String query(String targetUrl) throws Exception {
    URL url = new URL(targetUrl);
    return IOUtils.toString(url.openStream(), StandardCharsets.UTF_8);
}
```

---

## 三、规范执行要点

### 代码审查检查点
- [ ] 文件路径是否做了 toRealPath/canonicalPath 规范化
- [ ] 规范化后路径是否以基础目录开头（防路径遍历）
- [ ] 上传文件是否白名单校验类型 + UUID 重命名
- [ ] 网络请求目标是否做了白名单校验（防 SSRF）
- [ ] 是否禁止了对内网 IP 的访问
- [ ] 网络请求是否设置了 connectTimeout + socketTimeout
