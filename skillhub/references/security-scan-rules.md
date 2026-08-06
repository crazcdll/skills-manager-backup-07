# 安全扫描规则说明

## 目录

1. [规则体系概览](#规则体系概览)
2. [评分体系](#评分体系)
3. [规则详细说明](#规则详细说明)
   - [EX — Exfiltration（数据外传）](#ex--exfiltration数据外传)
   - [PE — Privilege Escalation（权限提升）](#pe--privilege-escalation权限提升)
   - [PS — Persistence（持久化）](#ps--persistence持久化)
   - [PI — Prompt Injection（提示词注入）](#pi--prompt-injection提示词注入)
   - [OB — Obfuscation（混淆）](#ob--obfuscation混淆)
   - [SC — Supply Chain（供应链）](#sc--supply-chain供应链)
   - [SL — Secret Leak（凭据泄露）](#sl--secret-leak凭据泄露)
   - [OP — Overpermission（权限过大）](#op--overpermission权限过大)
   - [QA — Quality（质量）](#qa--quality质量)
   - [MT — 美团内部专项](#mt--美团内部专项)
4. [特殊规则逻辑](#特殊规则逻辑)
5. [内网域名白名单机制](#内网域名白名单机制)
6. [Stage 2 深度阅读 FP 消除](#stage-2-深度阅读-fp-消除)

---

## 规则体系概览

`publish.py` 内嵌 30+ 条来自 `friday-skill-scanner` 的静态扫描规则，`security-check.py` 额外提供 5 条美团内部专项规则。规则 ID 遵循 cc-audit 体系。

| 类别 | 规则数 | 严重度 | 说明 |
|---|---|---|---|
| EX（Exfiltration） | 7 | FAIL/WARN | 网络外传、DNS 隧道、webhook、云存储 |
| PE（Privilege Escalation） | 6 | FAIL/WARN | sudo、rm -rf、chmod 777、SSH 等 |
| PS（Persistence） | 5 | FAIL | crontab、shell profile、systemd 等 |
| PI（Prompt Injection） | 8 | FAIL/WARN | 指令覆盖、HTML 注入、zero-width、RTL、DAN 等 |
| OB（Obfuscation） | 7 | FAIL/WARN | eval/exec、base64、hex/octal 等 |
| SC（Supply Chain） | 4 | FAIL/WARN | curl\|bash、不受信任包源 |
| SL（Secret Leak） | 4 | FAIL/WARN | 凭据文件、硬编码 key、敏感关键词 |
| OP（Overpermission） | 2 | WARN | 无工具限制、高危工具 |
| QA（Quality） | 3 | WARN | description 质量、文件数/大小 |
| MT（美团内部） | 5 | FAIL/WARN | 内网域名、AK/SK、appkey、命令注入、数据合规 |

---

## 评分体系

| 结果 | 加分 | 说明 |
|---|---|---|
| FAIL | +40 | 严重风险，发布被阻断 |
| WARN | +10 | 中等风险，提示后允许发布 |
| PASS | +0 | 无风险 |

**风险等级阈值**：

| 分值范围 | 等级 |
|---|---|
| 0 | safe |
| 1–25 | low |
| 26–50 | medium |
| 51–75 | high |
| 76–100 | critical |

---

## 规则详细说明

### EX — Exfiltration（数据外传）

| 规则 ID | 说明 | 严重度 | 触发模式 |
|---|---|---|---|
| EX-001 | 携带环境变量的网络请求 | FAIL | `curl $ENV_VAR`、`$VAR curl` |
| EX-002 | Base64 编码后传输 | FAIL | `base64 \| curl`、`echo \| base64 \| wget` |
| EX-003 | DNS 隧道外传 | FAIL | `dig $VAR`、`.exfil.`、`.dns.` 等 |
| EX-004 | 外部网络调用 | WARN | `curl`、`wget`、`fetch(`、`requests.`、`axios` 等 |
| EX-005 | Netcat 出站连接 | FAIL | `nc -e`、`ncat`、`socat`、`/dev/tcp/` |
| EX-006 | Webhook 外传服务 | FAIL | `webhook.site`、`requestbin`、`ngrok.io` 等 |
| EX-007 | 云存储上传 | FAIL | `aws s3 cp`、`gsutil cp`、`az storage blob` |

**修复建议**：
- EX-001/EX-002/EX-003/EX-005/EX-006/EX-007：删除相关代码或改为使用美团内部服务
- EX-004：确认调用是否必要；若只调用内网服务，文件中需包含内网域名（触发白名单机制）

### PE — Privilege Escalation（权限提升）

| 规则 ID | 说明 | 严重度 | 触发模式 |
|---|---|---|---|
| PE-001 | sudo 执行 | WARN | `sudo ` |
| PE-002 | 破坏性文件操作 | WARN | `shutil.rmtree`、`fs.unlinkSync`、`dd if=/dev/urandom` |
| PE-002b | 根文件系统 rm | FAIL | `rm -rf /`、`rm -rf /*` |
| PE-003 | 不安全权限修改 | FAIL | `chmod 777`、`chmod 666`、`chown root` |
| PE-004 | 系统密码文件访问 | FAIL | `/etc/passwd`、`/etc/shadow`、`/etc/sudoers` |
| PE-005 | SSH 目录访问 | FAIL | `.ssh/id_rsa`、`.ssh/authorized_keys` 等 |
| PE-006 | 库注入 | FAIL | `LD_PRELOAD`、`DYLD_INSERT_LIBRARIES` |

**修复建议**：
- PE-002b/PE-003/PE-004/PE-005/PE-006：删除相关代码，这类操作不应出现在 Skill 中
- PE-001：确认 sudo 是否必要；若必须，在 SKILL.md 中说明原因

### PS — Persistence（持久化）

| 规则 ID | 说明 | 严重度 | 触发模式 |
|---|---|---|---|
| PS-001 | Crontab 操纵 | FAIL | `crontab`、`/etc/cron.` |
| PS-003 | Shell 配置修改 | FAIL | `.bashrc`、`.zshrc`、`.bash_profile` |
| PS-004 | 系统服务注册 | FAIL | `systemctl enable`、`launchctl load` |
| PS-005 | SSH authorized_keys 修改 | FAIL | `authorized_keys` |
| PS-007 | 后台进程执行 | FAIL | `nohup`、`setsid`、`screen -dm` |

**修复建议**：持久化操作不应出现在 Skill 脚本中（`setup-scheduler.py` 等辅助工具是设计允许的例外，但需明确说明）。

### PI — Prompt Injection（提示词注入）

| 规则 ID | 说明 | 严重度 | 扫描范围 |
|---|---|---|---|
| PI-001 | 忽略指令模式 | FAIL | md_no_ref |
| PI-002 | HTML 注释隐藏指令 | FAIL | 所有 .md |
| PI-003 | 不可见 Unicode 字符 | FAIL | 所有文件（跳过含 CJK 的文件） |
| PI-004 | 角色劫持 | FAIL | md_no_ref |
| PI-005 | DAN/越狱变体 | FAIL | md_no_ref（过滤安全上下文行） |
| PI-006 | 系统提示词标记 | FAIL | 所有 .md |
| PI-007 | 工具描述污染 | FAIL | 所有 .md |
| PI-008 | 编码后的注入指令 | WARN | md_no_ref |

**修复建议**：
- PI-001/PI-004/PI-005：检查 SKILL.md 是否包含试图操控 AI 行为的文本
- PI-003：检查文件中是否存在零宽字符或 RTL override 字符

### OB — Obfuscation（混淆）

| 规则 ID | 说明 | 严重度 | 触发模式 |
|---|---|---|---|
| OB-001 | eval 变量 | WARN | `eval $VAR`、`eval "..."` |
| OB-002 | Base64 解码后执行 | FAIL | `base64 -d \| bash`、`base32 -d \| sh` |
| OB-003 | Hex/Octal 编码 | WARN | `echo -e '\x41'`、`printf '\x41'` |
| OB-004 | 字符串操作混淆 | WARN | `rev`、`IFS=`、`cut \| bash` |
| OB-005 | 通用 eval/exec | WARN | `eval(`、`exec(`、`Function(`、`__import__` |
| OB-006 | 进程替换执行 | WARN | `cat <(...) \| bash` |
| OB-007 | chr() 混淆 | WARN | `chr(65)+chr(66)` |

**修复建议**：
- OB-002：删除 base64 解码后直接执行的代码
- OB-005：避免使用 `eval`/`exec` 处理用户输入

### SC — Supply Chain（供应链）

| 规则 ID | 说明 | 严重度 | 触发模式 |
|---|---|---|---|
| SC-001 | curl 管道执行 | FAIL | `curl ... \| bash`、`wget ... \| python` |
| SC-002 | 不可信包源 | WARN | `pip install https://`、`npm install git+` |
| SC-003 | 自定义包索引 | FAIL | `--index-url`、`--extra-index-url`、`git+https://.#egg=` |
| SC-004 | setup.py post-install hook | WARN | `class Install`、`cmdclass=...install` |

**修复建议**：
- SC-001：禁止从网络获取脚本并直接执行
- SC-003：删除自定义包索引，使用官方 PyPI/npm 源

### SL — Secret Leak（凭据泄露）

| 规则 ID | 说明 | 严重度 | 触发模式 |
|---|---|---|---|
| SL-001 | 凭据文件访问 | WARN/FAIL | `.ssh/`、`.env`、`.aws/credentials`、`.docker/config.json` |
| SL-002 | 硬编码密钥 | FAIL | `AKIA...`（AWS）、`ghp_...`（GitHub Token）、`sk-...`（OpenAI）、`BEGIN PRIVATE KEY` |
| SL-003 | 代码中的敏感关键词 | WARN | `token="`、`secret="`、`password="` 等 |
| SL-004 | 环境变量读取 | WARN | `os.environ`、`process.env`、`$TOKEN`、`$SECRET` |

> **SL-001 升级规则**：若同一 code 文件中同时出现凭据文件访问 + 外部网络调用（且非内网域名），则升级为 FAIL。

**修复建议**：
- SL-002：删除所有硬编码密钥，改为从环境变量或配置读取
- SL-003：避免将敏感值直接赋值给变量

### OP — Overpermission（权限过大）

| 规则 ID | 说明 | 严重度 | 触发条件 |
|---|---|---|---|
| OP-001 | 无工具限制 | WARN | SKILL.md frontmatter 无 `allowed-tools` 字段 |
| OP-002 | 高危工具 | WARN | `allowed-tools` 包含 `Bash`/`Write`/`exec`/`shell` |

**修复建议**：在 SKILL.md frontmatter 中添加 `allowed-tools` 字段，明确声明所需工具。

### QA — Quality（质量）

| 规则 ID | 说明 | 严重度 | 触发条件 |
|---|---|---|---|
| QA-001 | description 过短 | WARN | < 20 字符 |
| QA-002 | description 过长 | WARN | > 500 字符 |
| QA-003 | 文件数/大小超限 | WARN | 文件数 > 50 或总大小 > 2MB |

### MT — 美团内部专项

由 `security-check.py` 执行，针对美团内部安全合规要求：

| 规则 ID | 说明 | 严重度 | 触发模式 |
|---|---|---|---|
| MT-001 | 内网域名硬编码 | WARN | `https://*.sankuai.com`、`*.meituan.com` 等 |
| MT-002 | 美团 AK/SK 泄露 | FAIL | `ak="{20+位字符}"`、`secret_key="..."` |
| MT-003 | Appkey 硬编码 | WARN | `com.sankuai.*`、`com.meituan.*` |
| MT-004 | 命令注入风险 | FAIL | `eval(input)`、`exec(sys.argv)` 等 |
| MT-005 | PII 数据合规 | WARN | 处理用户 PII 数据但未在 frontmatter 声明 |

**修复建议**：
- MT-001：内网 URL 改为配置项或使用 `mtskills` 内置认证
- MT-002：删除硬编码 AK/SK，改为环境变量
- MT-003：Appkey 通过 `--ciba` 参数或配置项传入
- MT-004：避免对用户输入直接 eval/exec

---

## 特殊规则逻辑

### PI-003（不可见 Unicode）

跳过含有 CJK 字符的文件（避免中文文档误报）。

CJK 范围：`[\u4E00-\u9FFF\u3400-\u4DBF\uF900-\uFAFF]`（中文、韩文、日文等）

### PI-005（DAN 越狱）

过滤安全上下文行：含 `check`、`verify`、`dangerous`、`prevent`、`avoid`、`never`、`should not` 等词的行被认为是安全讨论，不计入违规。

### SL-001（凭据文件访问）

- code 文件中出现 + 同文件有外部网络调用（非内网）：**FAIL**
- 仅 md 文件或仅凭据路径（无外传组合）：**WARN**

### MX-001（Markdown 危险命令）

仅扫描 `.md` 文件中**代码块外**的行（` ``` ` 围栏内代码跳过），避免误报文档示例。

---

## 内网域名白名单机制

`code_no_internal` scope 的规则（EX-001、EX-004）**对含有美团内网域名的文件免扫**，避免合法内网调用误报。

白名单域名：`*.sankuai.com`、`*.meituan.com`、`*.neixin.cn`、`localhost`、`127.0.0.1`、RFC1918 私有地址段（10.x、172.16-31.x、192.168.x）

> 如果你的 Skill 只访问内网服务，在代码文件中包含内网域名即可触发白名单，EX-001/EX-004 不会误报。

---

## Stage 2 深度阅读 FP 消除

`publish.py` 在 Stage 1 扫描后自动执行 Stage 2 深度阅读，分析每个 FAIL/WARN 匹配的上下文（±10 行），消除常见误报：

| 规则 | 典型误报场景 | 消除条件 |
|---|---|---|
| EX-004 | 注释/print 中的 URL | 行以 `#`、`//` 开头；含 `echo`/`print` |
| PE-001 | 文档中提到 sudo | 行以注释开头；含 `echo`/`print`/`建议` |
| PE-002 | 临时目录清理 | 含 `temp`、`tmp`、`cleanup`、`atexit` |
| PE-005 | 文档中提到 SSH 路径 | 行以注释开头；含 `edit`、`config`、`add` |
| SL-002 | 示例/测试中的密钥占位符 | 含 `example`、`test`、`sample`、`sk-xxx` |
| SC-001 | 注释中的 curl\|bash | 行以 `#`、`//` 开头 |

深度阅读降级后会在输出中标注 `[deep-read: downgraded]`，方便排查。
