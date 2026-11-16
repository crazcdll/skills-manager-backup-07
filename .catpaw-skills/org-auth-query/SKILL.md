---
name: org-auth-query
description: 权限相关触发场景：用户提到查询权限、根据mis 查权限、根据mis 查权限查询负责的权限应用信息、根据appId/clientId 查权限、应用数据权限、org 权限查询、查询员工鉴权信息、查询组织鉴权信息、根据mis查询申请单据。ORG API接口使用触发场景:员工信息接口使用、组织信息接口使用、jobCode岗位信息服务、SiteCode服务办公地址信息、公司信息服务查询、字典服务查询、员工证件服务查询、大区区域划分服务查询、特殊接口查询、点评/ID映射服务查询、代理商接口查询、Http 接口使用查询、数据权限申请变更、ORG SDK接入方法。通过 Python 脚本直接调用 org API 完成数据权限信息查询、ORG AP接口使用。

metadata:
  skillhub.creator: "wb_zhuhongxin"
  skillhub.updater: "wb_zhuhongxin"
  skillhub.version: "V29"
  skillhub.source: "FRIDAY Skillhub"
  skillhub.skill_id: "30229"
  skillhub.high_sensitive: "false"
---

# org-auth-query

## 📚 本地缓存文档（优先使用，无需再访问学城）

> 同步时间：2026-04-13 | 回答 ORG API 相关问题时，**先读本地文件**，无需访问学城

| 文件路径 | 内容 | 大小 |
|----------|------|------|
| `~/.openclaw/org-sdk-1-emp.md` | 员工服务接口（query/batchQuery/scroll/条件查询/搜索等） | 75KB |
| `~/.openclaw/org-sdk-2-org.md` | 组织服务接口（query/batchQuery/树形/路径/滚动查询等） | 30KB |
| `~/.openclaw/org-sdk-3-other.md` | 其他服务接口（JobCode/SiteCode/字典/证件/公司/ID映射等） | 79KB |
| `~/.openclaw/org-sdk-4-http.md` | HTTP 接口使用说明 | 10KB |
| `~/.openclaw/org-dict-main.md` | ORG2.0 数据字典（Emp/Org/EmpPos/JobCode等全部字段说明） | 62KB |
| `~/.openclaw/org-sdk-setup.md` | **SDK 接入方法**（POM依赖/Bean注入/接口调用/新老服务接入/调用示例） | 13KB |
| `~/.openclaw/org-auth-apply.md` | **数据权限申请/变更**（首次申请/权限修改入口/自查工具地址） | 1KB |

> 原始文档来源：
> - [0 - ORG2.0 SDK接口文档](https://km.sankuai.com/collabpage/58590434)（已拆分为子文档 237229893 / 237413937 / 237392972 / 162573936）
> - [3 - ORG2.0 数据字典](https://km.sankuai.com/collabpage/58898967)
> - [SDK接入方法](https://km.sankuai.com/collabpage/879599219)
> - [ORG接入权限申请或修改](https://km.sankuai.com/collabpage/1369442726)

---

支持 5 类能力：
1. 按 mis 查询权限应用列表
2. 按 clientId / appId 查询应用数据权限信息
3. 查询员工鉴权信息
4. 查询组织鉴权信息
5. 按 mis 查询权限申请单据信息

## 接口

- mis 查询
  - 线上：`https://org.sankuai.com/org/api/index/resources`
  - 线下：`https://org.it.test.sankuai.com/org/api/index/resources`
- app 前置校验
  - 线上：`https://org.sankuai.com/org/api/manage/application`
  - 线下：`https://org.it.test.sankuai.com/org/api/manage/application`
- app 数据权限查询
  - 线上：`https://org.sankuai.com/org/api/manage/applyInfo`
  - 线下：`https://org.it.test.sankuai.com/org/api/manage/applyInfo`
- 员工鉴权信息
  - 线上：`https://org.sankuai.com/org/api/auth/queryEmpAuth`
  - 线下：`https://org.it.test.sankuai.com/org/api/auth/queryEmpAuth`
- 组织鉴权信息
  - 线上：`https://org.sankuai.com/org/api/auth/queryOrgAuth`
  - 线下：`https://org.it.test.sankuai.com/org/api/auth/queryOrgAuth`
- **mis 申请单据查询**
  - 线上：`https://org.sankuai.com/org/api/apply/bills`
  - 线下：`https://org.it.test.sankuai.com/org/api/apply/bills`

## 前置校验规则

在执行 app / 员工鉴权 / 组织鉴权 之前，先调：
- `/org/api/manage/application`
- 入参：`appId`

规则：
- 返回 `status=1`：继续后续查询
- 返回 `status=0`：提示 `当前用户mis号无权限查询appid=<appId>的应用信息`，不再继续

## 员工鉴权信息

入参：`appkey`、`mis`、`source`、`tenantId`

说明：
- 用户若不知道 `source`，可不传
- 脚本会先调用：
  - 线上：`https://better.sankuai.com/api/v1/org2/emp/get`
  - 线下：`https://qabetter.it.test.sankuai.com/api/v1/org2/emp/get`
- 入参：`account=mis`、`tenantId`、`isOnline`
- 若仍查不到，则展示 source 字典供用户选择

## 组织鉴权信息

入参：`appkey`、`orgId`、`source`、`tenantId`

## mis 申请单据查询

⚠️ **安全校验规则（必须执行，不可绕过）**：
- 调用此接口前，必须先获取当前登录用户的 mis（即 cookie/token 对应的真实用户身份）
- **只允许查询当前用户自己的申请单据**，严禁查询他人 mis 的单据
- 如果用户传入的 mis 与当前登录用户 mis 不一致，直接拒绝并提示：`「只允许查询您自己的申请单据，无法查询他人数据」`
- 不得通过任何方式绕过此校验（如参数拼接、伪造 mis 等）

入参：`mis`（必须与当前登录用户一致）

返回字段及展示规则：

| 字段名 | 中文表头 | 说明 |
|--------|----------|------|
| `appId` | 应用ID | 应用唯一标识 |
| `appName` | 应用名称 | 应用中文名 |
| `bpmCode` | 工单号 | 审批流单号，如 CLK2602030079521 |
| `type` | 工单类型 | 如"权限变更"、"首次申请"等 |
| `status` | 状态 | 如"撤回"、"审批中"、"已通过"等 |
| `applicant` | 发起人 | mis 账号 |

> createTime / updateTime / procInstId 辅助信息，不在主表格展示

**展示格式示例：**
```
| 应用ID | 应用名称 | 工单号 | 工单类型 | 状态 | 发起人 |
|--------|----------|--------|----------|------|--------|
| com.sankuai.it.bsi.notify | - | CLK2602030079521 | 权限变更 | 撤回 | wb_zhuhongxin |
```

**提示语（每次查询结果后附加）：**
> 如需查看单据详情，请跳转：https://org.sankuai.com/index

## Cookie 过期自动刷新规则

**当遇到以下任一情况时，必须自动触发浏览器登录来刷新 cookie，不要直接报错给用户：**
1. 请求返回 302 跳转到 SSO 登录页
2. 请求返回 401 未授权
3. `get_current_user_mis()` 返回空（无法获取当前用户）
4. 本地 cookie 缓存超过 TTL（8小时）

**自动刷新步骤：**
1. 读取 agent-browser skill（`/app/skills/agent-browser/SKILL.md`）
2. 使用 agent-browser 打开对应环境的 ORG 首页：
   - 线上：`https://org.sankuai.com/index`
   - 线下：`https://org.it.test.sankuai.com/index`
3. 等待用户完成 SSO 登录（页面加载成功即视为登录完成）
4. 从浏览器获取最新 cookie，更新到 `~/.openclaw/org-auth-offline-cookie.json`
5. 使用新 cookie 重新执行原始查询

**重要**：整个刷新过程对用户透明，完成后直接返回查询结果，不需要用户手动操作。

## 线下环境认证

线下环境支持自动浏览器登录、Cookie 缓存、401/302 自动刷新。

## 示例

```bash
python3 scripts/org_auth_query.py mis wb_zhuhongxin --token "${user_access_token}"
python3 scripts/org_auth_query.py app mtupm --token "${user_access_token}"
python3 scripts/org_auth_query.py empauth --appkey mtupm --mis wb_zhuhongxin --source MT --tenantId 1 --token "${user_access_token}"
python3 scripts/org_auth_query.py orgauth --appkey mtupm --orgId 1 --source MT --tenantId 1 --token "${user_access_token}"
```

## ⚠️ 重要注意事项

- **mis 可能发生变化，员工唯一标识请用 `empId`，不要用 `mis`**
- 分页接口有限制：`offset < 5000`，超出数据查不到（需要白名单，联系 wb_liuhao13 / wb_zhuhongxin）
- **SDK 版本要求 5.0.0 以上**（因 OCTO TLS 要求），参考 [ORG SDK5.0.0 升级SOP](https://km.sankuai.com/page/1307684642)

---

## 参数定义

### EmpCond — 员工查询过滤条件

```java
public class EmpCond {
    EmpCond or(EmpCond cond);                              // 逻辑或
    EmpCond emailIn(List<String> emails);                  // 邮箱批量查询
    EmpCond personalEmailIn(List<String> emails);          // 个人邮箱批量查询
    EmpCond mobileIn(List<String> mobiles);                // 手机号批量查询
    EmpCond misIn(List<String> mises);                     // MIS号批量查询
    EmpCond joinDateBefore(Date date);                     // 入职时间早于(含)
    EmpCond joinDateAfter(Date date);                      // 入职时间晚于(含)
    EmpCond leftDateBefore(Date date);                     // 离职时间早于(含)
    EmpCond leftDateAfter(Date date);                      // 离职时间晚于(含)
    EmpCond transdateBefore(Date date);                    // 转正时间早于(含)
    EmpCond transdateAfter(Date date);                     // 转正时间晚于(含)
    // 员工类型(joinStatusId)：101劳动合同制 102待入职校招 103非全日制 104项目实习
    //   105校招实习 106客服待入职实习 131劳务派遣 134劳务人员 140退休返聘
    //   141兼职 142顾问 143外包 144人员外包 145项目外包 272代理商员工
    EmpCond joinStatusIdET(Integer joinStatusId);
    EmpCond joinStatusIdIn(List<Integer> joinStatusIds);
    // 在职状态(jobStatusId)：15 在职，16 离职
    EmpCond jobStatusIdET(Integer jobStatusId);
    EmpCond siteCodeIdET(String siteCode);
    EmpCond siteCodeIdIn(List<String> siteCodes);
    EmpCond cityIdET(String city);
    EmpCond cityIdIn(List<String> citys);
    EmpCond gbCityCodeET(String gbCityCode);               // 国标城市 2.4.3版+
    EmpCond gbCityCodeIn(List<String> gbCitys);
    EmpCond jobCodeIdET(String jobCodeId);
    EmpCond jobCodeIdIn(List<String> jobCodeIds);
    EmpCond jobGroupIdET(String jobGroup);
    EmpCond jobGroupIdIn(List<String> jobGroups);
    EmpCond jobFamilyIdET(String jobFamily);               // 码值: https://km.sankuai.com/collabpage/1444616305
    EmpCond jobFamilyIdIn(List<String> jobFamilys);
    EmpCond birthdayET(Date date);
    EmpCond birthdayBefore(Date date);
    EmpCond birthdayAfter(Date date);
    EmpCond pinyinIn(List<String> name);
    EmpCond nameIn(List<String> name);
}
```

### OrgCond — 组织查询过滤条件

```java
public class OrgCond {
    OrgCond or(OrgCond cond);
    OrgCond headET(String empId);                          // 根据组织首长查直接组织
    OrgCond headIn(List<String> empIds);
    OrgCond hrbpET(String empId);                          // 根据HRBP查组织
    OrgCond hrbpIn(List<String> empIds);
    OrgCond headJobNumberET(String jobNumber);              // 根据组织首长工号查组织
    OrgCond headJobNumberIn(List<String> jobNumbers);
    // status: 1=正常，0=失效
    OrgCond statusET(Integer status);
    // type: 0=正常组织，1=独立虚拟组织，2=非独立虚拟组织
    OrgCond typeET(Integer type);
    OrgCond typeIn(List<Integer> types);
    OrgCond levelET(String level);                         // ⚠️ 后期会下线，不建议使用
    OrgCond levelIn(List<String> levels);
    OrgCond categoryIdET(String categoryId);               // 码值表: https://km.sankuai.com/collabpage/1501638727
    OrgCond categoryIdIn(List<String> categoryIds);
}
```

### JobCodeCond — 岗位查询过滤条件

```java
public class JobCodeCond {
    // status: 1=正常，0=失效
    JobCodeCond statusET(Integer status);
}
```

### SiteCodeCond — 办公地址查询过滤条件

```java
public class SiteCodeCond {
    SiteCodeCond or(SiteCodeCond cond);
    SiteCodeCond statusIN(List<Integer> statusList);
    SiteCodeCond districtIdET(String districtId);
    SiteCodeCond districtIdIn(List<String> districtIds);
    SiteCodeCond cityIdET(String cityId);
    SiteCodeCond cityIdIn(List<String> cityIds);
    SiteCodeCond provinceIdET(String provinceId);
    SiteCodeCond provinceIdIn(List<String> provinceIds);
    SiteCodeCond areaIdET(String areaId);
    SiteCodeCond areaIdIn(List<String> areaIds);
    SiteCodeCond regionIdET(String regionId);
    SiteCodeCond regionIdIn(List<String> regionIds);
    SiteCodeCond countryIdET(String countryId);
    SiteCodeCond countryIdIn(List<String> countryIds);
}
```

### Paging — 分页参数

```java
public class Paging {
    Integer offset = 0;   // 从第几条开始（从0开始），⚠️ 限制 offset < 5000
    Integer size = 20;    // 单次查询数量，限制 1～500
    List<Sort> sort;      // 排序，-降序/+升序，多字段逗号分隔
}
public class Sort {
    String field;               // 排序字段名，来源于各实体静态成员，如 Emp.MIS
    SortDirection sortDirection; // 升序/降序
}
```

### Match — 关键字搜索条件

```java
public class Match {
    String keyword;          // 关键字
    List<String> fields;     // 指定搜索字段（可选）
    MatchType matchType;     // 匹配类型
}
public enum MatchType {
    match_phrase_prefix,  // 前缀匹配
    match_phrase          // 全匹配
}
```

### EmpLevel — 员工职级枚举

```java
enum EmpLevel {
    P1_0, P1_1, P1_2, P1_3,
    P2_1, P2_2, P2_3,
    P3_1, P3_2, P3_3,
    P4_1, P4_2, P4_3,
    P5_1,
    M1_0, M1_1, M1_2, M1_3,
    M2_1, M2_2, M2_3,
    M3_1, M3_2, M3_3,
    M4_1, M4_2, M4_3,
    M5_1,
    L0, L1, L2, L3, L4, L5, L6, L6A, L6B, L7, L8, L8A, L8B, L9, L10, L11, L12, L13, L14, L15
}
```

---

## Emp 对象字段说明

> 完整数据字典：[3 - ORG2.0 数据字典](https://km.sankuai.com/collabpage/58898967#id-3.1Emp)

| 字段 | 类型 | 说明 | 密级 |
|------|------|------|------|
| `tenantId` | Integer | 租户ID，1=美团，2=猫眼 | - |
| `source` | String | 数据域/业务类型 | - |
| `empId` | String | 员工ID（**唯一标识，推荐使用**） | - |
| `jobNumber` | String | 工号 | - |
| `name` | String | 姓名 | C-2 |
| `mis` | String | MIS账号（⚠️ 可能变化，勿作唯一标识） | C-2 |
| `pinyinName` | String | 姓名拼音 | C-2 |
| `pinyinXing` | String | 拼音姓（5.0.26版+） | C-2 |
| `pinyinMing` | String | 拼音名（5.0.26版+） | C-2 |
| `enName` | String | 英文名 | C-2 |
| `displayName` | String | 显示名 | C-2 |
| `gender` | Integer | 性别：0=未知，1=男，2=女（5.0.23版+） | C-2 |
| `birthday` | Date | 生日（年月日，格式 2023-12-15 00:00:00） | C-3 |
| `welfareBeginDate` | Date | 福利开始时间 | C-3 |
| `firstWorkDate` | Date | 首次工作时间 | C-3 |
| `email` | String | 工作邮箱 | C-3 |
| `personalEmail` | String | 个人邮箱 | C-3 |
| `mobile` | String | 手机号（**脱敏值**，明文需调 `empDataDecode`） | C-2 |
| `deskPhone` | String | 座机号 | C-2 |
| `jobStatusId` | Integer | **在职状态ID：15=在职，16=离职** | - |
| `jobStatus` | String | 在职状态名称 | - |
| `joinStatusId` | Integer | 员工类型ID（见 EmpCond 注释） | - |
| `joinStatus` | String | 员工类型名称 | - |
| `joinDate` | Date | 入职日期 | C-3 |
| `leftDate` | Date | 离职日期 | C-3 |
| `transDate` | Date | 转正日期 | C-3 |
| `recruit` | String | 招募渠道 | - |
| `siteCodeId` | String | 办公地点ID | - |
| `siteCodeName` | String | 办公地点名称 | - |
| `cityId` | String | 城市ID | - |

---

## 员工基本信息、职务信息领域查询接口

> 详情见文档：[1. 员工服务接口](https://km.sankuai.com/collabpage/237229893)

### 单员工查询

| 方法 | 说明 |
|------|------|
| `Emp query(String id, Date snapshot)` | 根据ID查询员工 |
| `Emp queryByJobNumber(String jobNumber, Date snapshot)` | 根据工号查询员工 |
| `Emp queryByMis(String mis, Date snapshot)` | 根据MIS号查询员工 |

### 批量员工查询

| 方法 | 说明 |
|------|------|
| `List<Emp> batchQuery(List<String> empIds, Date snapshot)` | 根据ID批量查询员工 |
| `List<Emp> batchQueryByJobNumber(List<String> jobNumbers, Date snapshot)` | 根据工号批量查询员工 |
| `List<Emp> batchQueryByMis(List<String> mises, Date snapshot)` | 根据MIS号批量查询员工 |

### 条件/组织查询

| 方法 | 说明 |
|------|------|
| `EmpItems query(EmpCond cond, Paging paging, Date snapshot)` | 属性过滤查询员工 |
| `EmpItems queryByOrgIds(List<String> orgIds, EmpCond cond, Paging paging, Date snapshot)` | 根据组织ID查询员工（仅主岗，不含子组织） |
| `EmpItems queryEmp(String orgId, Integer depth, EmpHierarchyCond cond, Paging paging)` | 根据orgId查询组织（含子组织）下的员工，仅限主岗 |
| `EmpItems queryByOrgHead(String headEmpId, Integer depth, EmpHierarchyCond cond, Paging paging)` | 根据组织首长查询组织下员工，仅限主岗 |
| `EmpItems queryBySiteCode(String siteCodeId, EmpCond cond, Paging paging, Date snapshot)` | 根据SiteCode查询员工 |
| `EmpItems queryByCity(String cityId, EmpCond cond, Paging paging, Date snapshot)` | 根据City查询员工 |

### 汇报链/下属查询

| 方法 | 说明 |
|------|------|
| `List<Emp> queryReportChain(String empId, Date snapshot)` | 查询员工主岗汇报链 |
| `EmpItems querySubordinates(String empId, Integer depth, EmpHierarchyCond cond, Paging paging)` | 查询员工主岗汇报下属 |
| `EmpItems querySubordinatesByEmpPosId(String empPosId, Integer depth, EmpHierarchyCond cond, Paging paging)` | 查询员工某个岗位的汇报下属 |
| `Emp queryHrbp(String empId, Date snapshot)` | 根据员工ID查询组织的HRBP |

### 搜索接口

| 方法 | 说明 |
|------|------|
| `EmpItems search(String keyword, EmpCond cond, Paging paging)` | 关键字搜索员工（支持手机号、MIS、姓名、拼音、邮件） |
| `EmpItems search(List<String> orgIds, String keyword, EmpCond cond, Paging paging)` | 关键字搜索员工（限制搜索组织范围，含子组织） |
| `EmpItems search(Match match, EmpCond cond, Paging paging)` | 关键字搜索员工（指定属性） |
| `EmpItems search(List<String> orgIds, Match match, EmpCond cond, Paging paging)` | 关键字搜索员工（指定属性 + 组织范围） |

### 岗位查询

| 方法 | 说明 |
|------|------|
| `EmpPosItems queryEmpPos(EmpPosCond cond, Paging paging, Date snapshot)` | 属性过滤查询岗位 |
| `List<EmpPos> queryEmpPos(String empId, Date snapshot)` | 主兼岗查询 |
| `Map<String, List<EmpPos>> batchQueryEmpPos(List<String> empIds, Date snapshot)` | 批量查询主兼岗 |
| `EmpPosItems queryEmpPoses(String orgId, Paging paging, Date snapshot)` | 根据组织ID查询员工岗位（不含子组织） |
| `List<EmpPos> queryVirtualEmpPos(String empId, Date snapshot)` | 根据员工ID获取虚拟组织岗位 |
| `List<EmpPos> queryAllEmpPos(String empId, Date snapshot)` | 根据员工ID获取所有岗位（实体主兼岗 + 虚拟组织岗位） |
| `Map<String, List<EmpPos>> batchQueryAllEmpPos(List<String> empIds, Date snapshot)` | 根据员工ID列表获取所有岗位 |

### 银行卡查询

| 方法 | 说明 |
|------|------|
| `List<BankCard> queryBankCard(String empId, Date snapshot)` | 根据员工ID查询银行卡信息 |
| `Map<String, List<BankCard>> batchQueryBankCard(List<String> empIds, Date snapshot)` | 根据员工ID批量查询银行卡信息 |

### 证件查询

| 方法 | 说明 |
|------|------|
| `Cert queryCert(String empId, CertType certType, Date snapshot)` | 根据员工ID和证件类型查询证件信息 |
| `List<Cert> queryCert(String empId, Date snapshot)` | 根据员工ID查询个人所有证件信息 |
| `Map<String, List<Cert>> batchQueryCert(List<String> empIds, Date snapshot)` | 根据员工ID批量查询证件信息 |
| `List<Emp> queryByCert(String code, CertType certType, Date snapshot)` | 根据证件号和证件类型查询员工信息 |

### 手机号/加密数据

| 方法 | 说明 |
|------|------|
| `String empDataDecode(String empId, String field)` | 员工数据手机号查询真实值 |
| `EmpMobile empMobileNumber(String empId, String field)` | 按员工ID查询明文手机号、区号信息 |
| `Map<String, String> batchEmpDataDecode(List<String> empIds, String field)` | 批量根据员工ID查询手机号真实值 |
| `String empDataEncrypt(String empId, String field)` | 查询员工加密数据 |

### 职级查询

| 方法 | 说明 |
|------|------|
| `EmpItems queryEmpByLevel(List<EmpLevel> levelList, String orgId, Integer depth, Paging paging)` | 根据组织ID和职级查询员工信息 |
| `List<Emp> filterEmpByLevel(List<String> empIds, List<EmpLevel> levelList, Date snapshot)` | 根据职级和员工ID查询员工信息 |
| `EmpItems filterEmpByLevel(EmpCond empCond, List<EmpLevel> levelList, Paging paging, Date snapshot)` | 根据职级和其它条件查询员工 |
| `EmpLevelCategory queryLevelCategory(String empId, Date snapshot)` | 查询员工岗位类型 |
| `List<EmpLevelCategory> batchQueryLevelCategory(List<String> empIds, Date snapshot)` | 批量查询员工岗位类型 |

### 关系判断

| 方法 | 说明 |
|------|------|
| `Boolean relationship(String empId1, String empId2, EmpRelationship relationship)` | 判断员工1是否是员工2的某种关系 |

### 滚动查询（大批量同步/异步）

| 方法 | 说明 |
|------|------|
| `EmpScrollItems scrollQueryFirst(List<String> orgIdList, EmpCond empCond, Paging paging, Date snapshot)` | 【同步 step1】员工首次滚动查询全量 |
| `EmpScrollItems scrollQuery(String scrollId, Paging paging, Date snapshot)` | 【同步 step2～N】员工滚动查询全量 |
| `void scrollQueryAsync(List<String> orgIdList, EmpCond empCond, Long snapshot, ScrollQuerySubscriber subscriber)` | 【异步】员工滚动查询全量 |

### ResponseResult 封装查询

| 方法 | 说明 |
|------|------|
| `ResponseResult queryByEmpIdResult(String empId, Date snapshot)` | 根据ID查询员工（ResponseResult封装） |
| `ResponseResult queryByMisResult(String mis, Date snapshot)` | 根据MIS查询员工（ResponseResult封装） |
| `ResponseResult batchQueryByEmpIdResult(List<String> empIds, Date snapshot)` | 根据ID批量查询员工（ResponseResult封装） |
| `ResponseResult batchQueryByMisResult(List<String> mises, Date snapshot)` | 根据MIS批量查询员工（ResponseResult封装） |

## 组织领域信息查询接口

> 详情见文档：[2. 组织服务接口](https://km.sankuai.com/collabpage/237413937)

### 单/批量组织查询

| 方法 | 说明 |
|------|------|
| `Org query(String id, Date snapshot)` | 根据ID查询组织 |
| `List<Org> batchQuery(List<String> ids, Date snapshot)` | 根据ID批量查询组织 |
| `OrgItems query(OrgCond cond, Paging paging, Date snapshot)` | 根据组织属性条件批量查询组织（分页） |
| `List<Org> queryRoot()` | 查询根组织 |

### 层级/树形查询

| 方法 | 说明 |
|------|------|
| `OrgItems queryBySuperior(String id, Integer dept, OrgHierarchyCond cond, Paging paging)` | 根据上级组织查询子组织（不含本身） |
| `List<Org> querySuperior(String id)` | 查询上级组织（不含本身） |
| `Hierarchy<Org> queryOrgTree(String id, Integer dept, OrgHierarchyCond cond)` | 根据上级组织查询子组织树（含本身） |
| `Hierarchy<OrgEmp> queryOrgEmp(String orgId, OrgHierarchyCond orgCond, EmpHierarchyCond empCond)` | 根据组织ID查询组织人员树（Deprecated） |
| `Hierarchy<OrgEmp> queryOrgEmp(String orgId, Integer depth, OrgHierarchyCond orgCond, EmpHierarchyCond empCond)` | 根据组织ID查询组织人员树 |

### 路径/关键字查询

| 方法 | 说明 |
|------|------|
| `Org queryByNamePath(String orgNamePath)` | 根据orgNamePath查询组织信息 |
| `OrgItems queryByNamePath(String pathName, OrgCond orgCond, Paging paging)` | 根据pathName分页查询有效/失效组织信息 |
| `OrgItems search(String keyword, OrgCond cond, Paging paging)` | 关键字搜索查询组织 |
| `OrgItems search(Match match, OrgCond cond, Paging paging)` | 关键字搜索查询组织（指定属性） |

### 可见组织树查询

| 方法 | 说明 |
|------|------|
| `List<Hierarchy<Org>> queryVisibleOrgs(String empId)` | 查询一个人可见的组织树（过时，不允许新接入） |
| `Hierarchy<Org> queryVisibleOrgs(String ssoId, String orgId, Integer depth, OrgHierarchyCond cond)` | 查询当前登录用户可见组织树（过时，不允许新接入） |
| `Hierarchy<OrgNode> queryVisibleOrgs(String ssoId, String orgId, Integer depth, OrgVisibleCond cond)` | 查询当前登录用户可见组织树（推荐） |
| `List<OrgNode> queryVisibleRoots(String ssoId, OrgHierarchyCond cond)` | 查询当前登录用户可见的根组织 |
| `VisibleOrgsConfig queryVisibleOrgsConfig(String mis, String orgId)` | 根据MIS和orgId查询可见组织配置 |

### 滚动查询（大批量同步/异步）

| 方法 | 说明 |
|------|------|
| `OrgScrollItems scrollQueryFirst(List<String> orgIdList, OrgCond orgCond, Paging paging, Date snapshot)` | 【同步 step1】组织首次滚动查询全量 |
| `OrgScrollItems scrollQuery(String scrollId, Paging paging, Date snapshot)` | 【同步 step2～N】组织滚动查询全量 |
| `void scrollQueryAsync(List<String> orgIdList, OrgCond orgCond, Long snapshot, ScrollQuerySubscriber subscriber)` | 【异步】组织滚动查询全量 |

## JobCode 岗位信息服务

> 详情见文档：[3. 其他服务接口](https://km.sankuai.com/collabpage/237392972)

| 方法 | 说明 |
|------|------|
| `JobCode query(String id, Date snapshot)` | 根据ID查询JobCode |
| `JobGroup queryJobGroup(String id, Date snapshot)` | 根据ID查询JobGroup |
| `JobFamily queryJobFamily(String id, Date snapshot)` | 根据ID查询JobFamily |
| `List<JobCode> batchQuery(List<String> ids, Date snapshot)` | 根据ID批量查询JobCode |
| `JobCodeItems queryByJobGroup(String jobGroupId, JobCodeCond cond, Paging paging, Date snapshot)` | 根据JobGroup批量查询JobCode |
| `JobGroupItems queryByJobFamily(String jobFamilyId, JobGroupCond cond, Paging paging, Date snapshot)` | 根据JobFamily查询JobGroup |
| `JobCodeItems queryJobCode(JobCodeCond cond, Paging paging, Date snapshot)` | 分页查询所有JobCode |
| `JobGroupItems queryJobGroup(JobGroupCond cond, Paging paging, Date snapshot)` | 分页查询所有JobGroup |
| `JobFamilyItems queryJobFamily(JobFamilyCond cond, Paging paging, Date snapshot)` | 查询所有JobFamily |

## SiteCode 服务办公地址信息

> 详情见文档：[3. 其他服务接口](https://km.sankuai.com/collabpage/237392972)

### SiteCode / 房间

| 方法 | 说明 |
|------|------|
| `SiteCode query(String id, Date snapshot)` | 根据ID查询SiteCode |
| `List<SiteCode> batchQuery(List<String> ids, Date snapshot)` | 根据办公区ID批量查询SiteCode |
| `SiteCodeItems query(SiteCodeCond cond, Paging paging, Date snapshot)` | 根据SiteCode属性条件批量查询（分页） |
| `SiteCodeItems search(Match match, SiteCodeCond cond, Paging paging)` | 关键字搜索SiteCode |
| `Room queryRoom(Integer id, Date snapshot)` | 根据房间ID查询房间 |
| `List<Room> batchQueryRoom(List<Integer> ids, Date snapshot)` | 根据房间ID批量查询房间 |
| `RoomItems queryRoom(String siteCodeId, Paging paging, Date snapshot)` | 根据SiteCode ID查询房间单元（仅有效房间） |
| `RoomItems queryRoom(String siteCodeId, RoomCond cond, Paging paging, Date snapshot)` | 根据SiteCode ID查询房间单元 |

### 国家/省份/城市/区县

| 方法 | 说明 |
|------|------|
| `CountryItems queryCountry(Paging paging, Date snapshot)` | 查询所有国家 |
| `Country queryCountry(String countryCode, Date snapshot)` | 根据国家code查询国家 |
| `List<Country> batchQueryCountry(List<String> countryCodes, Date snapshot)` | 根据国家code批量查询国家 |
| `ProvinceItems queryProvince(String countryId, Paging paging, Date snapshot)` | 根据国家查询省份 |
| `Province queryProvince(String provinceCode, Date snapshot)` | 根据省份code查询省份 |
| `List<Province> batchQueryProvince(List<String> provinceCodes, Date snapshot)` | 根据省份code批量查询省份 |
| `ProvinceItems searchProvince(String keyword, ProvinceCond cond, Paging paging)` | 关键字搜索省份 |
| `CityItems queryCity(String provinceId, Paging paging, Date snapshot)` | 根据省查询城市 |
| `City queryCity(String cityCode, Date snapshot)` | 根据城市code查询城市 |
| `List<City> batchQueryCity(List<String> cityCodes, Date snapshot)` | 根据城市code批量查询城市 |
| `CityItems searchCity(String keyword, CityCond cond, Paging paging)` | 关键字搜索城市 |
| `DistrictItems queryDistrict(String cityId, Paging paging, Date snapshot)` | 根据城市查询区县 |
| `District queryDistrict(String districtCode, Date snapshot)` | 根据区（县）code查询区（县） |
| `List<District> batchQueryDistrict(List<String> districtCodes, Date snapshot)` | 根据区（县）code批量查询区（县） |
| `DistrictItems searchDistrict(String keyword, DistrictCond cond, Paging paging)` | 关键字搜索区县 |

## 公司信息服务

> 详情见文档：[3. 其他服务接口](https://km.sankuai.com/collabpage/237392972)

| 方法 | 说明 |
|------|------|
| `Comp query(String id, Date snapshot)` | 根据ID查询公司 |
| `List<Comp> batchQuery(List<String> ids, Date snapshot)` | 根据ID批量查询公司 |
| `CompItems pagingQuery(CompCond compCond, Paging paging, Date snapshot)` | 分页查询所有公司 |

## 字典服务

> 详情见文档：[3. 其他服务接口](https://km.sankuai.com/collabpage/237392972)

| 方法 | 说明 |
|------|------|
| `Dict query(String id, Date snapshot)` | 根据ID查询字典 |
| `List<Dict> batchQuery(List<String> ids, Date snapshot)` | 根据ID批量查询字典 |
| `DictItems query(DictCond dictCond, Paging paging, Date snapshot)` | 分页查询所有字典 |
| `DictItems queryByCategory(String categoryId, DictCond dictCond, Paging paging, Date snapshot)` | 根据类别查询所有字典 |

## 员工证件服务

> 详情见文档：[3. 其他服务接口](https://km.sankuai.com/collabpage/237392972)

| 方法 | 说明 |
|------|------|
| `CertItems CertService.query(CertCond cond, Paging paging, Date snapshot)` | 属性过滤查询证件 |

## 大区区域划分服务

> 详情见文档：[3. 其他服务接口](https://km.sankuai.com/collabpage/237392972)

| 方法 | 说明 |
|------|------|
| `Area queryAreaBySiteCode(String siteCode, Date snapshot)` | 根据SiteCode查询区域 |
| `Area queryArea(String areaCode, Date snapshot)` | 根据区域code查询区域 |
| `Region queryRegion(String regionCode, Date snapshot)` | 根据大区code查询大区 |

## 特殊接口

> 详情见文档：[4. 特殊接口（已过时）](https://km.sankuai.com/collabpage/162573936)

| 方法 | 说明 |
|------|------|
| `SensitiveTokenData getToken(String empId, SensitiveDataType sensitiveDataType)` | 通过员工ID获取token数据 |
| `SensitiveEncryptData getTokenAndEncrypt(String empId, SensitiveDataType sensitiveDataType)` | 通过员工ID获取token和密文数据 |
| `SensitiveDecodeData getPlainText(String encryptStr, SensitiveDataType sensitiveDataType)` | 通过密文获取明文数据 |
| `String msgDecrypt(String cyphertext, String type)` | 对密文进行解密（已过时） |
| `String msgEncrypt(String plaintext, String type)` | 对明文进行加密（已过时） |
| `FutureOrg queryFutureOrg(String psOrgId)` | 根据ID查询未来生效组织 |
| `String sendSms(String empId, String paramJson)` | 发送短信验证码（需申请真实手机号权限） |
| `String sendSmsBySso(String ssoId, String paramJson)` | 发送短信验证码 |
| `String checkSmsCode(String empId, String smsCode, String paramJson)` | 验证短信验证码 |

## ID映射服务

> 详情见文档：[5. ORG2.0 support-lib SDK接口文档](https://km.sankuai.com/collabpage/92930183)

| 方法 | 说明 |
|------|------|
| `String mapping(String id, CommonMappingType type)` | 单个ID映射 |
| `Map<String, String> mapping(List<String> ids, CommonMappingType type)` | 批量ID映射 |
| `Map<String, String> mapping(CommonMappingType type)` | 全量获取ID映射 |
| `String dictMapping(String dictCatagory, String id, DictMappingType type)` | 单个dictCategory映射 |
| `Map<String, String> dictMapping(String dictCatagory, List<String> ids, DictMappingType type)` | 批量dictCategory映射 |
| `Map<String, String> dictMapping(String dictCatagory, DictMappingType type)` | 全量dictCategory映射 |
| `DataConfig queryDataConfig(String id, ObjectClass objectClass)` | 根据ID查询指定对象的配置项目 |
| `Map<String, DataConfig> batchQueryDataConfig(List<String> ids, ObjectClass objectClass)` | 批量查询指定对象的数据配置项 |
| `Integer queryTenantId(String code, IDType idType)` | 查询指定标识对应的租户ID |
| `Map<String, Integer> batchQueryTenantId(List<String> codes, IDType idType)` | 批量查询指定标识对应的租户ID |
| `Boolean isSales(String orgId, Date snapshot)` | 销售组织判断 |
| `Map<String, Boolean> isSales(List<String> orgIds, Date snapshot)` | 批量销售组织判断 |

## 代理商接口

| 方法 | 说明 |
|------|------|
| `Boolean empExist(String empId)` | 判断员工是否存在（包含未入职员工） |
| `List<EmpPosHistory> queryEmpPosHistory(String empId)` | 根据员工ID查询岗位历史列表 |
| `List<OrgHistory> queryOrgHistory(String orgId)` | 根据ID查询组织历史列表 |
| `String generateJobNumber(String empId)` | 生成员工工号 |
| `String generateOrgId()` | 生成组织ID |
| `String generateJobFamilyId()` | 生成员工岗位大类 JobFamilyId |
| `String generateJobGroupId()` | 生成员工岗位所属小类ID JobGroupId |
| `String generateJobCodeId()` | 生成员工岗位ID JobCodeId |

## HTTP 接口使用查询

> 详情见文档：[1. ORG2.0 HTTP接口文档](https://km.sankuai.com/collabpage/121665947)
