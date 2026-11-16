# 规则包后台预取指南(Step 2I 背景与设计说明)

> 本文档是 SKILL.md Step 2I 的背景资料,**执行契约(命令/退出码/收割动作)以 SKILL.md 2I 段为准**。排查预取问题、调整链路时阅读本文。

## 产品决策记录

- **只要 L2**(2026-09-22 定):调封装脚本时固定传 `--l2-only`,公司级 L1 规范不落盘不注入。理由:L1 规范已有 `references/checklists/mt-java-coding-standards/` 本地快照支撑 Step 4-B,平台 L1 注入会重复;L2 团队规范是增量信息
- **L2 与仓库自定义规则分开存放**:L2 → `/tmp/cr_l2_rules_{prId}.md`,仓库自定义 → `/tmp/cr_custom_rules_{prId}.md`。采纳率可分「平台 L2 命中」vs「仓库自定义(CU:)命中」两个口径
- **fe 边界**(2026-09-22 拍板):纯前端路由主流程不预取、不传 L2,规则获取由 fe-ai-review 内部自理;混合 PR 主流程拉到的 L2 原样透传给 fe
- **失败永不阻塞**:任何失败(未装/超时/rc≠0)→ kill 后台任务、回退仓库内已有规则,禁止重试禁止中止
- **后续要上 L1 时**:去掉 `--l2-only` 并恢复 4-C 的 L1 注入策略即可,脚本无需改动

## 为什么空目录就够

官方 Runner(`mt-code-standards-setup` 的 `sync-effective-rules-with-sso.mjs`)优先使用 `--repository`,按仓库标识拉取,不需要本地仓库或 clone。因此:

- `$CR_RULES_OUT` 空目录直接作为输出目录
- `--repo-root` 是兼容参数:只用于 Git 探测,并在未传 `--output-dir` 时充当输出基目录;输出优先级 `--output-dir` > `--repo-root` > 当前目录
- `--domain` 只在未传 locator、或 bootstrap 且非 Git 目录时需要;已登记仓库的 resolve 会直接返回 `standard_domain`
- ⚠️ 若未来需要真实 clone:沙箱内 **https git clone 会被代理拦截超时,必须用 SSH 地址**(实测结论,2026-09-22)

## 平台契约速查

- API host:`https://db0y7dgg85gphojyva.database.sankuai.com/functions/v1/rule-distribution`
- resolve:`POST /v1/effective-rule-bundles/resolve`(一次返回 L1+L2,无「只拉 L2」开关——l2-only 的丢弃发生在封装脚本落盘层)
- bootstrap:`POST /v1/l1-rule-bundles/bootstrap`(仅 L1)
- **未登记仓库**:resolve 返回 `repository_not_registered` 时 Runner 降级 l1_bootstrap(仅 L1)。l2-only 下 team/ 为空属正常结果,Step 4-C 按无 L2 处理
- **仓库订阅关系**:L2 按服务端「仓库→规则集」订阅关系返回,有组织关联校验(forbidden/not_associated)
- **DOMAIN_CONFIRMATION**:仓库 domain 判不出时 Runner 返回 `RULE_BUNDLE_DOMAIN_CONFIRMATION_REQUIRED`→ 脚本退出码 5。2H 判 backend 时预传 `--domain backend` 规避
- scope_level 枚举只有 `["L1","L2"]`(源码 L422 校验),**平台无 L3 概念**——勿与 CR 的 Layer 3(业务语义)混淆

## 已知边界与风险

- **repo 存在性无服务端校验**:不存在的仓库与未登记仓库同返回 l1_bootstrap、同错误码 `repository_not_registered`,无法区分 → repo 名 typo 会静默降级为「无 L2」。(可选增强:Bitbucket REST API 预检,待拍板)
- **首次安装窗口**:未装 `@it/oa-skills` 时脚本内自动安装耗时 30-60s,可能超出收割窗口 → 该次收割视为超时降级,下次 CR 自然生效
- **认证**:沙箱 SANDBOX_ 环境走 mtsso-moa-local-exchange(official_moa_exchange);凭证 5 层 redact(access_token/Bearer/JWT),manifest 无敏感字段
- 平台侧留痕 pull_id,可在平台查拉取记录

## 封装脚本退出码契约

| 退出码 | 含义 | 主流程处理 |
|---|---|---|
| 0 | 成功(resolve 或 l1_bootstrap 都算) | 收割 team/ → l2_rules 缓存 |
| 2 | 参数错误 | 播报,回退 |
| 3 | mt-code-standards-setup 未装 | 播报提示跳过,回退 |
| 4 | 拉取失败/超时 | kill+播报,回退 |
| 5 | DOMAIN_CONFIRMATION(仅 mixed 未传 domain) | 播报,回退 |

## 产出物结构

```
$CR_RULES_OUT/                      # = $CR_RUN_DIR/rule_bundle
├── manifest.json                   # repo/mode/l1_files计数/l2_rule_sets/domain/pulled_at/l2_only(日志性质,L1 只留计数不留文件)
└── team/<规则集ID>/*.md            # L2 规则正文,唯一交付物
```

- l2-only 下 company/ 不 mv,Runner 落在 `.mdp/rules/company/` 的 L1 文件被 clean_internal(`rm -rf $OUT/.mdp`)整目录清除,**磁盘零残留**
- 脚本幂等:重跑先 `rm -rf team/company/manifest.json`,多仓串行场景每仓重置无互踩
