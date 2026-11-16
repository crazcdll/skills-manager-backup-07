## HA-05 缓存高可用规范（审查精要）

| 编号 | 规则 | 级别 |
|------|------|------|
| MT:HA-C001 | 缓存一致性必须用Cache Aside模式：读先缓存miss后DB回填；写先更新DB再删缓存 | P1 |
| MT:HA-C002 | BigKey治理：Squirrel String ≤512KB/元素 ≤5000，Cellar Value ≤10KB；Pipeline ≤512，multiGet ≤1024 | P1 |
| MT:HA-C003 | 缓存防护三件套：穿透（空值缓存/布隆过滤器）+ 击穿（互斥锁）+ 雪崩（TTL抖动） | P1 |
| MT:HA-C004 | 序列化必须版本兼容，禁止修改类全限定名，StoreKey必须用StoreKey(category,template)构建 | P1 |

### 强制禁止
- ✗ 禁止先删缓存再更新 DB（会导致并发脏数据）
- ✗ 禁止缓存不设置 TTL
- ✗ 禁止对大集合执行 O(N) 全量操作（HGETALL/SMEMBERS）
- ✗ 禁止 Pipeline 超过 512 个命令
- ✗ 禁止修改缓存对象的类全限定名
- ✗ 禁止使用 Squirrel pubsub
- ✗ 禁止缓存异常阻断主流程

### 检查点
- [ ] 缓存读写是否遵循 Cache Aside 模式
- [ ] 缓存是否设置了 TTL 且有随机抖动
- [ ] 是否存在 BigKey
- [ ] 是否有穿透/击穿防护
- [ ] 序列化对象的类名是否被修改
- [ ] 缓存异常是否被降级处理

→ 完整规则含示例见 mt-java-coding-standards/HA-05-缓存高可用规范.md
