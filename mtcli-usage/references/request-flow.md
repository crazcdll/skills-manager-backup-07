# 请求流程参考

用于 AI 已经锁定某个 `<service>.<resource>.<method>`，需要规划或执行一次 mtcli API 调用时。

## 安全第一步

不确定调用形态或副作用时，先 dry-run：

```bash
mtcli <service> <resource> <method> [flags] --dry-run
```

dry-run 只展示请求计划，通常包括：

- HTTP method
- 最终 URL
- query/header/path 参数
- request body
- auth type
- timeout

不要把 dry-run 当作远端 API 调用成功。

## 参数通道

动态命令有三种传参方式：

```bash
mtcli <service> <resource> <method> --<param> <value>
mtcli <service> <resource> <method> --params '<json-object>'
mtcli <service> <resource> <method> --headers '<json-object>'
```

body 只走 `--json`：

```bash
mtcli <service> <resource> <method> --json '<json-object>'
```

规则：

- path/query/header 的标量参数可能会生成业务独立 flag。
- object/array 这类复杂 path/query/header 参数走 `--params`。
- body 参数不生成业务独立 flag，使用 `--json`。
- 一旦提供 `--params`，它就是 path/query/header 的权威来源，不要和业务独立 flag 合并推断。
- `--headers` 专门用于传递 header 参数，优先级高于 `--params`（同名 header 以 `--headers` 为准）。
- JSON key 保持 schema 里的原始名字，不要随意改大小写。

使用示例：

```bash
# 使用 --headers 指定 header 参数（优先级最高）
mtcli <service> <resource> <method> --headers '{"X-Auth-Token": "<token>"}'

# --headers 与 --params 混用，同名 header 以 --headers 为准
mtcli <service> <resource> <method> --params '{"id": "123"}' --headers '{"X-Auth-Token": "<token>"}'

# 同时传递 header、path/query 和 body
mtcli <service> <resource> <method> \
  --params '{"id": "123", "page": 1}' \
  --headers '{"X-Auth-Token": "<token>"}' \
  --json '{"name": "test"}'
```

## 结构化输出

下游要解析结果时使用结构化输出：

```bash
mtcli <service> <resource> <method> --output json
```

## 真实执行

只有在 method、参数、鉴权和副作用都确认后，才执行真实调用：

```bash
mtcli <service> <resource> <method> [flags]
```

## 安全门控

- 明确只读的方法，dry-run 确认后通常可执行。
- 名称或描述包含 create/update/delete/modify/import/bind/publish/sync 等语义时，按有副作用处理。
- 用户只要求验证、查看或排查时，停在 dry-run 或 schema 检查，除非用户明确要求真实调用。
