# {{REPO_NAME}} 知识库索引

> 文档更新时间：{{TODAY}}
> Owner：{{OWNER}}
> 适用范围：`{{REPO_NAME}}` 仓库总索引
> 关联代码：`{{REPO_PATH}}`
> 关联文档：`knowledge/README.md`

本文档为仓库知识库总索引，负责串联页面主链路、核心模块、接口、状态和排障入口。

## 阅读建议

- 想快速知道仓库该怎么看：先读 `knowledge/onboarding/0-reading-path.md`
- 想理解页面如何启动和渲染：读 `knowledge/business/main-page.md`
- 想理解接口与数据来源：读 `knowledge/business/api-interfaces.md`
- 想理解状态管理：读 `knowledge/business/store-state.md`
- 想看具体模块：读 `knowledge/modules/`

## 目录结构

```text
knowledge/
  README.md
  Agent.md
  onboarding/
  business/
  modules/
  faq/
  adr/
  _templates/
```

## 业务逻辑索引

- 主页面：`knowledge/business/main-page.md`
- 接口：`knowledge/business/api-interfaces.md`
- 状态管理：`knowledge/business/store-state.md`
- 路由：`knowledge/business/routing.md`
- 公共工具：`knowledge/business/utils-tools.md`
- 性能：`knowledge/business/performance.md`
- 模块树总览：`knowledge/business/modules-desc.md`

## 模块索引

这里必须补页面从上到下的核心模块索引，建议按下列字段组织：

| 模块 | 代码路径 | 接口路径 | 关键字段 | 详细文档 |
|------|----------|----------|----------|----------|
| 示例模块 | `src/...` | `/api/example` | `data.title` | `knowledge/modules/example.md` |

## 核心接口速查

建议至少补一张速查表：

| 接口路径 | 用途 | 相关模块 |
|---------|------|---------|
| `/api/example` | 示例 | `example-module` |

## 关键状态速查

建议至少补一段状态结构或表格：

```text
state
├── page
├── list
└── user
```

## FAQ 与排障入口

- 高频问题：`knowledge/faq/common-questions.md`
- 排障手册：`knowledge/faq/troubleshooting.md`

## 跨端或环境差异

如果仓库存在多端差异，建议在此处补充一个速查表。
