# mtcli 命令模板速查

只作为 AI 内部速查。对用户展示时保留占位符，除非具体值来自用户。

## 基础探索

```bash
mtcli services
mtcli services --output json
mtcli schema <service>
mtcli schema <service>.<resource>.<method> --resolve-refs
```

## 鉴权

```bash
mtcli auth sso login [--mis <mis>]
mtcli auth sso logout
mtcli auth sso whoami
mtcli auth sso audience --url <url>
mtcli auth access whoami
```

## 动态服务调用

```bash
mtcli <service> <resource> <method> [flags]
mtcli <service> <resource> <method> --params '<json-object>'
mtcli <service> <resource> <method> --headers '<json-object>'
mtcli <service> <resource> <method> --json '<json-object>'
mtcli <service> <resource> <method> --mtcli-target-env prod-keeta --params '<json-object>'
mtcli <service> <resource> <method> --mtcli-schema-env prod --mtcli-target-env test --params '<json-object>'
mtcli <service> <resource> <method> --dry-run
```

常用 flags：

```bash
--timeout <seconds>
--mtcli-target-env <env>
--mtcli-schema-env <env>
--output json
-v
--no-cache
```

## tools 模式

```bash
mtcli tools describe <service>
mtcli tools call <service_resource_method> --params '<json-object>'
mtcli tools call <service_resource_method> --params '<json-object>' --json '<json-object>'
mtcli tools call <service_resource_method> --params '<json-object>' --dry-run
mtcli tools call <service_resource_method> --timeout <seconds>
```

## 缓存管理

```bash
mtcli cache list
mtcli cache refresh --service <service>
mtcli cache clear
```

## 输出判断

- 业务成功码因服务而异，不要只凭一个固定 code 判断。
- HTTP 401/403 或 auth envelope 优先按鉴权/权限处理。
- 返回 HTML 登录页通常表示该路径需要浏览器 session 或 cookie 形态鉴权。
