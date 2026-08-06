## SEC-A 注入安全规范（审查精要）

| 编号 | 规则 | 级别 |
|------|------|------|
| MT:SEC-A001 | 禁止将用户可控参数直接拼接到OS命令，优先用ProcessBuilder+白名单 | P0 |
| MT:SEC-A002 | XML解析必须禁用DTD和外部实体（XXE防护） | P0 |
| MT:SEC-A003 | SQL注入防护：首选#{}参数化，${}必须SecSdk白名单校验 | P0 |
| MT:SEC-A004 | Cookie必须设HttpOnly+Secure+SameSite；响应头含X-Content-Type-Options+X-Frame-Options+CSP | P0 |
| MT:SEC-A005 | URL重定向必须白名单校验，禁止开放重定向 | P0 |
| MT:SEC-A006 | POST/PUT/DELETE接口必须有CSRF防护（SameSite Cookie或Token校验） | P0 |

### 强制禁止
- ✗ 禁止将用户输入直接拼接到 OS 命令
- ✗ 禁止使用默认配置的 XML 解析器（XXE漏洞）
- ✗ 禁止 `${}` 无校验拼接 SQL
- ✗ 禁止 Cookie 不设 HttpOnly/Secure/SameSite
- ✗ 禁止缺少 X-Content-Type-Options / X-Frame-Options / CSP
- ✗ 禁止未验证的 URL 重定向
- ✗ 禁止状态改变接口无 CSRF 防护

### 检查点
- [ ] 是否存在 Runtime.exec() 直接拼接用户输入
- [ ] XML 解析器是否禁用了 DTD 和外部实体
- [ ] SQL 是否使用了 #{} 参数化绑定
- [ ] Cookie 是否设置了 HttpOnly + Secure + SameSite
- [ ] 响应头是否包含安全头
- [ ] URL 重定向是否做了白名单校验
- [ ] POST/PUT/DELETE 接口是否有 CSRF 防护

→ 完整规则含示例见 mt-java-coding-standards/SEC-A-注入安全规范.md
