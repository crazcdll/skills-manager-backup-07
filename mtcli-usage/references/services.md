# 服务可用性参考

不要在 skill 中维护具体服务清单、具体接口状态或历史测试结果。服务目录、schema、鉴权方式和可用性会变化，AI 应实时检查。

## 判断策略

1. 用户给了 `<service>`：优先检查该服务。
2. 用户只给业务领域：先列服务或搜索服务名，再让 schema 决定下一步。
3. 用户给了 `<service>.<resource>.<method>`：直接查 method schema。
4. 调用失败时，不要立刻认定服务不可用；先区分 schema、参数、鉴权、网络、权限和业务错误。

## 推荐检查顺序

```bash
mtcli <service> --help
mtcli schema <service>.<resource>.<method> --resolve-refs
mtcli tools describe <service>
mtcli <service> <resource> <method> --params '<json-object>' --dry-run
```

## 可用性信号

| 信号 | 说明 |
|---|---|
| schema 中 resources/methods 为空 | 可能未配置、缓存过期或服务暂无可用接口 |
| path 缺 host 或协议 | schema 配置可能有问题 |
| 401/403 | 鉴权或权限问题 |
| HTML 登录页 | 当前鉴权形态可能不被服务接受 |
| 404 | 可能是路径迁移、资源不存在或 schema 过期 |
| timeout/network | 可能是网络、环境或服务不可达 |

## 环境切换

如果用户要求切换业务目标环境，先看 schema/service config 是否支持目标环境。使用模板：

```bash
mtcli <service> <resource> <method> --mtcli-target-env <env> [flags]
```

`<env>` 是后端 `serviceConfig` key。国内地址通常沿用 `prod`、`test`、`staging`、`dev`；海外 region 通常使用 `<environment>-keeta`，例如 `prod-keeta`、`staging-keeta`、`test-keeta`、`dev-keeta`。不要假设所有服务都支持所有环境或 region。

如果用户要求“线上 schema + 线下地址”或其他拆分组合，使用 `--mtcli-schema-env` 单独指定 schema/config discovery 环境：

```bash
mtcli <service> <resource> <method> --mtcli-schema-env prod --mtcli-target-env test [flags]
```

注意区分鉴权：schema discovery SSO 跟随 schema env；业务接口 SSO 跟随 target env。

## 缓存修复

当服务 schema 看起来过期或与错误不符时，先刷新单个服务：

```bash
mtcli cache refresh --service <service>
```

不要使用全量 `mtcli cache refresh`；该路径已禁用。多服务排查时逐个刷新目标服务，或先使用轻量服务索引确认服务名。
