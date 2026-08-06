## HA-13 搜索引擎高可用规范（审查精要）

| 编号 | 规则 | 级别 |
|------|------|------|
| MT:HA-ES001 | 查询安全：禁止 from+size>10000 深分页（用search_after/scroll），filter替代must，terms ≤1024，scroll后必须清理 | P2 |
| MT:HA-ES002 | 写入安全：必须用Bulk批量+指定文档id（幂等），Bulk ≤10MB，失败项必须处理 | P2 |
| MT:HA-ES003 | Mapping安全：禁止修改已有字段类型，新增字段注意index属性，refresh_interval非实时建议30s，副本 ≥1 | P1 |
| MT:HA-ES004 | 容灾降级：Lion开关切流，Raptor告警（延迟/错误率/集群健康），关闭客户端自动重试 | P2 |

### 强制禁止
- ✗ 禁止 `from + size > 10000`（深分页会导致ES OOM）
- ✗ 禁止对 text 字段做精确匹配（应用 term + keyword）
- ✗ 禁止逐条写入 ES
- ✗ 禁止 Bulk 请求体超过 10MB
- ✗ 禁止修改已有字段的 Mapping 类型
- ✗ 禁止 ES 不配置容灾降级

### 检查点
- [ ] 查询是否存在深分页（from + size > 10000）
- [ ] 不需要评分的查询是否使用了 filter
- [ ] terms 元素是否超过 1024
- [ ] 写入是否使用 Bulk 且指定了文档 id
- [ ] Bulk 失败项是否有处理逻辑
- [ ] 是否配置了 ES 容灾降级开关
- [ ] scroll 查询是否及时清理

→ 完整规则含示例见 mt-java-coding-standards/HA-13-搜索引擎高可用规范.md
