---
ruleType: Model Request
description: 改pom.xml/引依赖/升版本时读我。强制SNAPSHOT限制、依赖升级管控、版本冲突检测、二方库稳定可追溯。新增或升级dependency前必读。
category: 依赖规范
priority: high
---

# 依赖管理规范

## SNAPSHOT版本限制

### N0004 [强制] 线上环境SNAPSHOT禁止规则

线上应用不要依赖SNAPSHOT版本（安全包除外）；正式发布的类库必须先去中央仓库进行查证，使RELEASE版本号有延续性，且非SNAPSHOT版本号不允许覆盖升级。

**说明**：不依赖SNAPSHOT版本是保证应用发布的幂等性。另外，也可以加快编译时的打包构建。

## 依赖升级管控

### N0005 [推荐] 依赖升级仲裁一致性规则

二方库的新增或升级，保持除功能点之外的其它jar包仲裁结果不变。如果有改变，必须明确评估和验证。

**操作步骤**：
1. 升级前执行 `mvn dependency:resolve > before.txt`
2. 升级后执行 `mvn dependency:resolve > after.txt`
3. 比对差异 `diff before.txt after.txt`
4. 如果仲裁结果完全不一致，使用 `mvn dependency:tree -Dverbose` 命令找出差异点
5. 进行 `<exclude>` 排除冲突的jar包

## 版本冲突检测

### N0006 [强制] 版本冲突禁止规则

禁止在子项目的pom依赖中出现相同的GroupId，相同的ArtifactId，但是不同的Version。可借助maven-enforcer-plugin强制检查插件识别jar包版本冲突。

## 枚举类型使用限制

### N0007 [推荐] 枚举类型使用规则

二方库里可以定义枚举类型，但是参数、返回值不允许使用枚举类型或者包含枚举类型的POJO对象，防止消费方无法枚举解析失败的问题。

**正例**：
```java
// 参数使用String
public void processOrder(String status) { }

// 返回值使用String
public String getOrderStatus() { return orderStatus.name(); }
```

## 二方库发布原则

### N0011 [推荐] 二方库发布稳定可追溯原则

每个版本的变化应该被记录，二方库由谁维护，源码在哪里，都需要能方便查到。除非用户主动升级版本，否则公共二方库的行为不应该发生变化。
