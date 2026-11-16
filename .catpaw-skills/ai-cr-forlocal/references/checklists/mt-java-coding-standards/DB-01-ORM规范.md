---
ruleType: Model Request
description: ORM开发规范，包含查询字段规范、SQL注入防护、类型安全结果集、DAO层代码生成工具使用规范（MDP/XFrame MyBatis Generator及MyBatis-Plus Generator）
category: ORM规范
priority: high
---

#### 规范作用域总则
| 代码来源 | 适用规范 |
|---------|---------|
| Generator（MBG/MP Generator）**自动生成的基础 CRUD 代码** | **豁免** java-l1:DB-01.ORM001、java-l1:DB-01.ORM002 —— 框架行为，不应手动修改 DO 类、Mapper 基础方法、XML 基础片段 |
| **AI 在 Mapper/XML 中新增的自定义查询方法** | **必须遵守** java-l1:DB-01.ORM001~java-l1:DB-01.ORM003 |
| Service 层及以上的业务代码 | **必须遵守** 全部规范 |

---

以下示例仅用于说明规则边界与意图，不代表唯一实现方式；实际生成或审查代码时，应优先复用项目现有框架、工具类、SDK 与命名，并以是否满足规则约束为判断标准。

**SQL 承载方式**：MyBatis 的 XML Mapper 与注解（`@Select` 等）均可，按团队既有约定选择，本规范不作强制；为与"AI 在 XML 中扩展自定义查询方法"的定位一致，下方示例统一采用 XML Mapper 写法。

### java-l1:DB-01.ORM001 [推荐] 建议明确指定查询字段，避免不必要的 SELECT *
**作用域：AI 编写的新增自定义查询方法（生成器基础代码豁免）**

**必须指定字段**：分页/列表查询、JOIN 关联查询、含 TEXT/BLOB/JSON 大字段的表、对外接口查询
**可接受全量字段**：单表主键查询、表结构稳定且 < 15 列的简单查询
**生成器豁免**：MBG 的 Base_Column_List、selectByPrimaryKey/selectByExample；MP 的 selectById/selectList 等基础方法不受约束

##### good case：
```xml
<!-- UserMapper.xml：列表/分页查询 —— 指定字段 -->
<select id="listByStatus" resultType="UserDO">
    SELECT id, name, email FROM user WHERE status = #{status}
</select>
```
##### bad case：
```xml
<!-- 大表列表用 SELECT * / 含大字段查询用 SELECT * -->
<select id="listOrdersByUser" resultType="OrderDO">
    SELECT * FROM order WHERE user_id = #{userId} LIMIT 100
</select>
<select id="getArticle" resultType="ArticleDO">
    SELECT * FROM article WHERE id = #{id}  <!-- 有 content TEXT 字段 -->
</select>
```

### java-l1:DB-01.ORM002 [强制] SQL参数使用#{}，禁止使用${}防止SQL注入
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

### java-l1:DB-01.ORM003 [推荐] 不允许直接使用 HashMap/Hashtable/Map 作为查询结果集输出
- 强类型 DO 类提供编译期检查和 IDE 提示；AI 无法感知数据库 Schema，手写 DO 容易出错，应优先用代码生成工具生成
- 例外：动态报表/通用查询返回结构不固定时，可酌情使用 Map

##### good case：
```java
public UserDO getUserById(Long id) { return userMapper.selectById(id); }
```
##### bad case：
```java
public HashMap<String, Object> getUserById(Long id) { return userMapper.selectById(id); }
public Map<String, Object> getUserById(Long id) { return userMapper.selectById(id); }
```

### java-l1:DB-01.ORM004 [推荐] DAO/Mapper 层基础代码优先用代码生成工具生成，AI 不应从头手写
**原因**：AI 看不到数据库 Schema，手写 DO/Mapper 易出现字段映射错误、类型不一致、JDBC Type 遗漏等问题；代码生成工具直接读取元数据，100% 准确。

**AI ✅ 可以做**：编写自定义业务 SQL（复杂 JOIN、统计报表）、在 XML 中扩展自定义查询方法、Service 层逻辑、SQL 性能优化
**AI ❌ 不该做**：从头手写 DO 类、Mapper 接口 + XML 映射文件、猜数据库字段名和 JDBC 类型、编写 Example/QueryWrapper 基础结构

##### good case：
```java
// Generator 生成基础 CRUD → AI 仅扩展自定义方法
public interface UserMapper extends MybatisBaseMapper<UserDO, UserExample, Long> {
    // 生成器自动生成的基础方法...
    List<UserDO> selectActiveUsersWithOrderCount(@Param("example") UserExample example); // AI 扩展 ✅
}
```
##### bad case：
```java
// ❌ AI 手写 DO —— 字段名/类型可能出错
public class UserDO { private Long id; private String userName; /* 可能与实际库不符 */ }
```

### java-l1:DB-01.ORM005 [推荐] 按项目框架选择正确的代码生成工具，生成前必须先阅读对应文档
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