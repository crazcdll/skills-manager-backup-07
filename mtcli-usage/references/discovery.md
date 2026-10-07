# 发现与 Schema 检查参考

用于 AI 需要发现服务、确认命令树、查看参数结构或判断是否能调用时。

## 起点

列出服务：

```bash
mtcli services
```

查看根帮助：

```bash
mtcli --help
```

查看服务命令树：

```bash
mtcli <service> --help
```

查看资源命令树：

```bash
mtcli <service> <resource> --help
```

## Schema 检查

查看服务资源/方法摘要：

```bash
mtcli schema <service>
```

查看资源：

```bash
mtcli schema <service>.<resource>
```

查看方法：

```bash
mtcli schema <service>.<resource>.<method>
```

展开 refs：

```bash
mtcli schema <service>.<resource>.<method> --resolve-refs
```

指定 schema/config discovery 环境：

```bash
mtcli --mtcli-schema-env <env> schema <service>.<resource>.<method> --resolve-refs
```

未传 `--mtcli-schema-env` 时，schema discovery 沿用 `--mtcli-target-env`。如果只想切业务目标地址，不想切 schema 来源，需要显式指定 `--mtcli-schema-env`。

需要这些信息时优先看 schema：

- 精确参数名
- 参数位置：path/query/header/body
- required/optional
- enum/default/format/deprecated
- `authType`：已按 method/resource/service 解析后的生效鉴权类型
- request/response schema
- body 复杂类型字段描述：`requestSchema.properties.<field>.description`
- body strict validation 是否开启

## 参数描述位置

- 单接口参数描述优先看 `mtcli schema <service>.<resource>.<method> --resolve-refs`。
- body 复杂类型字段描述在 `requestSchema.properties.<field>.description`；嵌套 `$ref` 字段需要 `--resolve-refs` 后查看展开结果。
- 直接查看类型定义可用 `mtcli schema <service>.<resource>.#<TypeName> --resolve-refs`，字段描述在 `properties.<field>.description`。
- `mtcli tools describe <service>` 也会在 `inputSchema.properties.<bodyParam>.properties.<field>.description` 展示 body 字段描述。
- 动态方法 `--help` 的 `Structured Params` 只做简要提示，可能不展示 body 字段 description；不要把它当作完整 schema 来源。

## 选择规则

- 用户只说业务领域：先服务发现。
- 用户给了 service 但没给 resource/method：看服务命令树或 tools describe。
- 用户给了 method 但没给参数：看 method schema。
- 用户是另一个 agent 或需要结构化 contract：用 tools describe。
- schema 和实际行为冲突：先单服务刷新缓存，再复查 schema。
- schema 来源环境可能影响可见服务和地址配置；线上 schema + 线下目标地址用 `--mtcli-schema-env prod --mtcli-target-env test`。
