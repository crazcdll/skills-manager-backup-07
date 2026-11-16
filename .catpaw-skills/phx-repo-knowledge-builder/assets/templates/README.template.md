# {{REPO_NAME}} Knowledge

> 文档更新时间：{{TODAY}}
> Owner：{{OWNER}}
> 适用范围：`{{REPO_NAME}}` 仓库知识库首页
> 关联代码：`{{REPO_PATH}}`
> 关联文档：`knowledge/Agent.md`

## 这是什么

这是 `{{REPO_NAME}}` 的仓库知识库，用于帮助团队快速理解仓库结构、页面主链路、核心模块、接口和排障入口。

## 适合谁看

- 新接手仓库的同学
- 需要评估改动影响面的同学
- 需要排查线上问题的同学

## 如何开始阅读

建议按下面顺序阅读：

1. `knowledge/Agent.md`
2. `knowledge/onboarding/0-reading-path.md`
3. `knowledge/business/main-page.md`
4. `knowledge/business/api-interfaces.md`
5. `knowledge/business/store-state.md`
6. `knowledge/modules/`

## 快速入口

- 页面主链路：`knowledge/business/main-page.md`
- 接口与数据：`knowledge/business/api-interfaces.md`
- 状态管理：`knowledge/business/store-state.md`
- 模块拆解：`knowledge/modules/`
- 排障入口：`knowledge/faq/troubleshooting.md`

## 目录说明

- `knowledge/Agent.md`
  - 总索引页
- `knowledge/onboarding/`
  - 新同学阅读路径和仓库地图
- `knowledge/business/`
  - 页面级和系统级知识
- `knowledge/modules/`
  - 模块级知识
- `knowledge/faq/`
  - 高频问题和排障
- `knowledge/adr/`
  - 关键设计决策

## 维护约定

- 改主链路时同步更新 `business/`
- 改核心模块时同步更新对应 `modules/`
- 新增复杂逻辑时补 FAQ 或 ADR
