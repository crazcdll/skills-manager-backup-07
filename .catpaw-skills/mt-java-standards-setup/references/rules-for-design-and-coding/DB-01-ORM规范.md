---
ruleType: Model Request
description: 写Mapper/DAO/MyBatis XML或手写SQL时读我。强制参数用#{}防SQL注入、按项目框架(MDP/XFrame)选对代码生成工具。出现${}拼接或字符串拼SQL时必读。
category: ORM规范
priority: high
---

#### 规范作用域总则
| 代码来源 | 适用规范 |
|---------|---------|
| Generator（MBG/MP Generator）**自动生成的基础 CRUD 代码** | **豁免** ORM002 —— 框架行为，不应手动修改 DO 类、Mapper 基础方法、XML 基础片段 |
| **AI 在 Mapper/XML 中新增的自定义查询方法** | **必须遵守** ORM002 |
| Service 层及以上的业务代码 | **必须遵守** 全部规范 |

---

以下示例仅用于说明规则边界与意图，不代表唯一实现方式；实际生成或审查代码时，应优先复用项目现有框架、工具类、SDK 与命名，并以是否满足规则约束为判断标准。

**SQL 承载方式**：MyBatis 的 XML Mapper 与注解（`@Select` 等）均可，按团队既有约定选择，本规范不作强制；为与"AI 在 XML 中扩展自定义查询方法"的定位一致，下方示例统一采用 XML Mapper 写法。

### ORM002 [强制] SQL参数使用#{}，禁止使用${}防止SQL注入
**作用域：AI 编写的新增自定义查询方法（生成器基础代码豁免）**

- `#{}` 预编译防注入，`${}` 存在 SQL 注入风险
- `${}` 仅可在动态表名/列名场景使用，且必须白名单校验
- **生成器豁免**：MBG 的 `order by ${orderByClause}` 属于框架内部行为（Example 对象控制），不约束；但 AI 新增自定义 SQL 中严禁 `${}` 拼接用户输入

##### good case：
```xml
<!-- UserMapper.xml：#{} 预编译防注入 -->
<select id="getById" resultType="UserDO">
    SELECT id, name, age FROM user WHERE id = #{id}
</select>
```
##### bad case：
```xml
<!-- ${} 拼接用户输入 —— SQL 注入风险 -->
<select id="getById" resultType="UserDO">
    SELECT id, name, age FROM user WHERE id = ${id}
</select>
```

### ORM005 [推荐] 按项目框架选择正确的代码生成工具，生成前必须先阅读对应文档
⚠️ AI 生成或修改 DAO 层代码前，**必须先阅读对应文档**！

| 项目类型 | 框架 | 工具 | 文档 | 命令 |
|---------|------|------|------|------|
| MDP | MyBatis | `mdp-mybatis-generator-maven-plugin` | [文档](https://km.sankuai.com/collabpage/424829078) | IDEA 双击 或 `mvn mdp-mybatis-generator:generate` |
| MDP | MyBatis-Plus | `mdp-boot-starter-mybatisplus` + 手动管依赖版本 | [文档](https://km.sankuai.com/collabpage/1830721014) | Mapper 继承 `EnhancedMapper<T>` |
| XFrame | MyBatis | `xframe.generator:mybatis-generator-maven-plugin` | [文档](https://km.sankuai.com/collabpage/360460185) | `mvn mybatis-generator:generate` |
| XFrame | MyBatis-Plus | `xframe:mybatisplus-generator-maven-plugin` | [文档](https://km.sankuai.com/collabpage/667003030) | `mvn mybatisplus-generator:generate` |

**MDP 要点**：必须用 MDP 封装版 MBG 插件（别名为 `record`，勿混用原生 `row`）；MP 需手动管理 mybatis 依赖版本且不能用 mybatis-config.xml
**XFrame 要点**：MP Generator 无需 generatorConfig.xml，配置在 pom `<configuration>` 中完成
**非 MDP/XFrame**：使用官方用法或询问用户
