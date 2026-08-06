## DEP-01 依赖管理规范（审查精要）

| 编号 | 规则 | 级别 |
|------|------|------|
| MT:N0001 | GroupId格式：`com.{公司}.业务线.[子业务线]`，最多4级 | P2 |
| MT:N0002 | ArtifactId格式：`产品线名-模块名`，语义不重复不遗漏 | P2 |
| MT:N0003 | Version格式：`主版本号.次版本号.修订号`，起始版本必须为 `1.0.0` | P2 |
| MT:N0004 | 线上应用禁止依赖SNAPSHOT版本（安全包除外），RELEASE版本不允许覆盖升级 | P0 |
| MT:N0005 | 二方库新增/升级必须保持仲裁结果不变，用diff比对 | P2 |
| MT:N0006 | 禁止相同GroupId+ArtifactId但不同Version共存（版本冲突） | P1 |
| MT:N0007 | 二方库参数/返回值不允许使用枚举类型或含枚举的POJO | P2 |
| MT:N0008 | 依赖声明放 `<dependencies>`，版本仲裁放 `<dependencyManagement>` | P2 |
| MT:N0009 | 不要使用不稳定或已过时的工具包/Utils类 | P2 |
| MT:N0010 | 二方库发布只含Service API/领域模型/Utils/常量/枚举，无log具体实现 | P2 |
| MT:N0011 | 二方库每个版本变化必须被记录，行为不应因用户未升级而变化 | P2 |

### 强制禁止
- ✗ 禁止线上应用依赖 SNAPSHOT 版本（安全包除外）
- ✗ 禁止相同 GAV 出现不同 Version（版本冲突）
- ✗ 禁止二方库参数/返回值使用枚举类型
- ✗ 禁止 RELEASE 版本覆盖升级
- ✗ 禁止使用不稳定/过时的工具包

### 检查点
- [ ] 是否存在 SNAPSHOT 依赖
- [ ] 是否存在版本冲突（相同 GAV 不同 Version）
- [ ] 二方库参数/返回值是否使用了枚举
- [ ] 版本仲裁是否在 dependencyManagement 中
- [ ] 二方库发布是否精简（无多余依赖）

→ 完整规则含示例见 mt-java-coding-standards/DEP-01-依赖规范.md
