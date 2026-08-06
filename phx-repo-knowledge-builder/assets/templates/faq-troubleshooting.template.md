# 排障手册

> 文档更新时间：{{TODAY}}
> Owner：{{OWNER}}
> 适用范围：`{{REPO_NAME}}` 常见排障入口
> 关联代码：`{{REPO_PATH}}`
> 关联文档：`knowledge/Agent.md`

## 问题 1：页面异常或空白

### 现象

待补充。

### 排查步骤

1. 看页面入口和初始化链路
2. 看关键接口是否返回
3. 看关键状态是否被正确更新
4. 看兜底逻辑是否生效

### 相关文档

- `knowledge/business/main-page.md`
- `knowledge/business/api-interfaces.md`
- `knowledge/business/store-state.md`

## 问题 2：核心模块不展示

### 现象

待补充。

### 排查步骤

1. 看模块数据源
2. 看模块显隐条件
3. 看接口失败兜底
4. 看跨端或 AB 条件

### 相关文档

- `knowledge/modules/`
- `knowledge/business/api-interfaces.md`
