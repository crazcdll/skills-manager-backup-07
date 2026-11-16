---
ruleType: Model Request
description: 依赖管理核心强制规范，包含GAV坐标定义、版本号管理、SNAPSHOT限制、依赖升级管控、版本冲突检测、枚举限制、POM结构等关键规则。适用于所有Java项目的Maven依赖管理。
category: 依赖规范
priority: high
---

# 依赖管理规范

## 依赖坐标定义规范

### java-l1:DEP-01.N0001 [推荐] GroupId格式定义

GroupId格式：`com.{公司}.业务线.[子业务线]`，最多4级，子业务线可选。

- **正例**：`com.meituan.service.mobile`、`com.sankuai.xm`
- **反例**：`com.sankuai.meituan.service.mobile`（sankuai和meituan重复导致层级过长）

### java-l1:DEP-01.N0002 [推荐] ArtifactId格式定义

ArtifactId格式：`产品线名-模块名`。语义不重复不遗漏，先到中央仓库查证。

- **正例**：`mtthrift`、`xxx-client`、`fastjson-api`、`jstorm-tool`

### java-l1:DEP-01.N0003 [强制] Version版本号格式定义

二方库版本号命名方式：`主版本号.次版本号.修订号`

**起始版本号必须为 `1.0.0`，而不是 `0.0.1`**

- **主版本号**：产品方向改变，或者大规模API不兼容，或者架构不兼容升级
- **次版本号**：保持相对兼容性，增加主要功能特性，影响范围极小的API不兼容修改
- **修订号**：保持完全兼容性，修复BUG、新增次要功能特性等
- **反例**：仓库内某二方库版本号从 `1.0.0.0` 开始，一直默默"升级"成 `1.0.0.64`，完全失去版本的语义信息

## SNAPSHOT版本限制

### java-l1:DEP-01.N0004 [强制] 线上环境SNAPSHOT禁止规则

线上应用不要依赖SNAPSHOT版本（安全包除外）；正式发布的类库必须先去中央仓库进行查证，使RELEASE版本号有延续性，且非SNAPSHOT版本号不允许覆盖升级。

**说明**：不依赖SNAPSHOT版本是保证应用发布的幂等性。另外，也可以加快编译时的打包构建。

## 依赖升级管控

### java-l1:DEP-01.N0005 [推荐] 依赖升级仲裁一致性规则

二方库的新增或升级，保持除功能点之外的其它jar包仲裁结果不变。如果有改变，必须明确评估和验证。

**操作步骤**：
1. 升级前执行 `mvn dependency:resolve > before.txt`
2. 升级后执行 `mvn dependency:resolve > after.txt`
3. 比对差异 `diff before.txt after.txt`
4. 如果仲裁结果完全不一致，使用 `mvn dependency:tree -Dverbose` 命令找出差异点
5. 进行 `<exclude>` 排除冲突的jar包

## 版本冲突检测

### java-l1:DEP-01.N0006 [强制] 版本冲突禁止规则

禁止在子项目的pom依赖中出现相同的GroupId，相同的ArtifactId，但是不同的Version。可借助maven-enforcer-plugin强制检查插件识别jar包版本冲突。

## 枚举类型使用限制

### java-l1:DEP-01.N0007 [推荐] 枚举类型使用规则

二方库里可以定义枚举类型，但是参数、返回值不允许使用枚举类型或者包含枚举类型的POJO对象，防止消费方无法枚举解析失败的问题。

**正例**：
```java
// 参数使用String
public void processOrder(String status) { }

// 返回值使用String
public String getOrderStatus() { return orderStatus.name(); }
```

## POM文件结构规范

### java-l1:DEP-01.N0008 [推荐] 依赖声明位置规则

所有pom文件中的依赖声明放在 `<dependencies>` 语句块中，所有版本仲裁放在 `<dependencyManagement>` 语句块中。

**说明**：
- `<dependencyManagement>` 里只是声明版本，并不实现引入，因此子项目需要显式的声明依赖，version和scope都读取自父pom
- `<dependencies>` 所有声明在主pom的 `<dependencies>` 里的依赖都会自动引入，并默认被所有的子项目继承

## 工具包选择原则

### java-l1:DEP-01.N0009 [推荐] 工具包稳定性规则

不要使用不稳定或者已过时的工具包或者Utils类。

## 二方库发布原则

### java-l1:DEP-01.N0010 [推荐] 二方库发布精简可控原则

为避免应用二方库的依赖冲突问题，二方库发布者应当遵循以下原则：

移除一切不必要的API和依赖，只包含Service API、必要的领域模型对象、Utils类、常量、枚举等。如果依赖其它二方库，尽量是provided引入，让二方库使用者去依赖具体版本号；无log具体实现，只依赖日志框架。

### java-l1:DEP-01.N0011 [推荐] 二方库发布稳定可追溯原则

每个版本的变化应该被记录，二方库由谁维护，源码在哪里，都需要能方便查到。除非用户主动升级版本，否则公共二方库的行为不应该发生变化。