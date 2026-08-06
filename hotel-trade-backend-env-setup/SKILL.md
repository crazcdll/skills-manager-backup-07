---
name: hotel-trade-backend-env-setup
description: 为酒店交易后端项目提供通用的开发机环境一键搭建与本地启动能力。只要用户提到酒店交易后端环境搭建、新电脑初始化、JDK8、Maven、MDP、本地启动 `trade-hotel-apic`、`hotel-order-xplus`、`hotel-order-query`、`hotel-order-search`、`trade-hotel-subsystem`、`trade-hotel-aggregate`、`hotel-order-apib` 等 Java 后端项目，或希望一套环境能复用到多个酒店交易后端仓库时，就应立即使用这个 skill。

metadata:
  skillhub.creator: "wangjinlong04"
  skillhub.updater: "wangjinlong04"
  skillhub.version: "V6"
  skillhub.source: "FRIDAY Skillhub"
  skillhub.skill_id: "87007"
---

# Hotel Trade Backend Env Setup

这个 skill 不再默认走临时沙盒运行，而是面向“新电脑初始化 + 多项目复用”的开发机环境搭建。

当前脚本路径仍保留为：

```bash
bash .catpaw/skills/trade-hotel-apic-local-start/scripts/apic_local_start.sh
```

这是为了兼容已有调用，但脚本已经支持酒店交易多个后端仓库。

## 目标能力

用一套用户级环境支持多个酒店交易后端项目：

- 安装或复用 JDK 8（不需要 JDK 17）
- JDK 8 下载优先走内网 s3plus 源，失败后回退 Azul Zulu API，再兜底 legacy 公网源
- 安装或复用 Maven 3.9.x
- 默认尊重用户已有环境，不主动改写 shell 启动文件
- 生成项目级 env 文件
- 自动识别 `plusboot.yaml`、`spring-boot-maven-plugin`、`ApplicationLoader`
- 对指定项目执行本地启动

## 安装范围

默认写入用户目录，而不是临时目录：

- 工具安装目录：`~/.hotel-trade/backend-env/`
- Maven 本地仓库：`~/.m2/repository`
- shell profile 片段：`~/.hotel-trade/backend-env/profile.sh`
- shell 启动文件：默认 `~/.zshrc`，也支持显式指定
- 项目 env 文件：`~/.hotel-trade/backend-env/projects/<repo>.env.sh`

## 适用项目

优先适用于当前工作区内这类酒店交易 Java/MDP 后端：

- `trade-hotel-apic`
- `trade-hotel-aggregate`
- `trade-hotel-subsystem`
- `hotel-order-apib`
- `hotel-order-xplus`
- `hotel-order-query`
- `hotel-order-search`
- `hotel-order-xpush`
- `hotel-order-generaltrade`
- `hotel-bizplatform-operation`

## 工作方式

### 1. 体检环境

如果用户想先看机器缺什么，执行：

```bash
bash .catpaw/skills/trade-hotel-apic-local-start/scripts/apic_local_start.sh doctor --repo /absolute/path/to/repo
```

输出重点：

- 目标项目需要的 JDK 版本（固定为 JDK 8）
- 目标项目的发布模块 `PUB_MODULE`
- 目标项目的启动类 `mainClass`
- 当前机器是否已有可用 JDK 8 / Maven
- `/data/webapps/appenv` 是否存在且已配置 `env=`
- 用户级安装目录
- `~/.m2/settings.xml` 是否存在
- 仓库代码权限是否正常
- 健康检查端口是否可能冲突
- 推荐下一步命令

### 2. 搭建通用后端环境

如果用户是新电脑初始化，执行：

```bash
bash .catpaw/skills/trade-hotel-apic-local-start/scripts/apic_local_start.sh setup --repo /absolute/path/to/repo
```

这个步骤会：

- 读取目标项目需要的 JDK / Maven
- 优先复用本机已有工具
- 只有缺失时才安装到 `~/.hotel-trade/backend-env`
- macOS 上优先尝试内网 s3plus 提供的 JDK 8 DMG；失败后自动查询 Azul Zulu API 获取可用 tar.gz 下载地址
- 若下载到损坏归档或错误版本，会自动删除缓存并切换下一个下载源
- 默认不改写 `~/.zshrc`
- 仅当显式传入 `--write-shell-rc` 时，才写入 `source` 语句
- 保留 `~/.m2/repository` 作为多个项目共享仓库

如果用户只是想先把通用环境准备好，不指定项目也可以执行：

```bash
bash .catpaw/skills/trade-hotel-apic-local-start/scripts/apic_local_start.sh setup
```

这时默认准备酒店交易常用的 JDK 8 + Maven 3.9.5。

### 重要：appenv 配置

后端服务本地启动依赖 `/data/webapps/appenv` 文件，该文件提供 `env`、`swimlane`、`zkserver` 等主机环境配置。

- 如果该文件不存在，skill 的 `doctor` 和 `start` 模式会给出警告，并附上配置文档链接
- 由于配置 appenv 需要创建 `/data` 软链接并重启电脑，**AI 无法自动完成**，需要用户手动操作
- 配置步骤详见：`https://km.sankuai.com/collabpage/2712812595`

### 3. 生成项目启动环境

如果用户已经有机器级环境，想给某个仓库生成运行 env，执行：

```bash
bash .catpaw/skills/trade-hotel-apic-local-start/scripts/apic_local_start.sh prepare --repo /absolute/path/to/repo
```

这个步骤会：

- 自动识别目标项目元信息
- 生成 `~/.hotel-trade/backend-env/projects/<repo>.env.sh`
- 固化 `JAVA_HOME`、`M2_HOME`、`HOST_ENV`、`PUB_MODULE`、`MAIN_CLASS`、`APPKEY`
- 如果用户已有环境，默认只生成项目 env，不改写 shell 启动文件

### 4. 一键启动项目

如果用户明确要把某个后端项目跑起来，执行：

```bash
bash .catpaw/skills/trade-hotel-apic-local-start/scripts/apic_local_start.sh start --repo /absolute/path/to/repo
```

执行要求：

- 优先使用用户现有的 JDK / Maven；缺失时才回退到 skill 管理目录中的工具
- 使用 `~/.m2/repository`，方便多个项目共享依赖
- 默认 `HOST_ENV=test`
- 默认不改写 shell 启动文件；仅当显式传入 `--write-shell-rc` 时才修改
- 使用项目发布模块执行 `spring-boot:run`
- 启动前自动检查 `~/.m2/settings.xml`
- 启动前自动检查健康检查端口是否已被占用
- 启动后自动轮询健康地址；如果项目提供了 `plusboot.yaml` 的 `TEST_URL`，优先使用它
- 探活失败时自动终止启动进程并给出失败提示

## 关键原则

- 默认是“用户级安装，可复用到多个项目”，不是临时沙盒
- 默认尊重用户已有环境：已有可用 JDK/Maven 时，不主动修改 `~/.zshrc`
- 只有本机缺少 Java 8 时才触发下载，且优先内网源，尽量减少重复失败重试
- 仅在用户显式要求时，才通过 `--write-shell-rc` 修改 shell 启动文件，或通过 `--target-home` / `--install-root` 做隔离测试
- 对新人电脑优先做 `doctor -> setup -> prepare -> start`
- 如果缺少 `~/.m2/settings.xml`，要明确提醒：JDK/Maven 已就绪，但内网 Maven 私服访问可能仍失败
- 如果仓库没有 clone / pull 权限，要指导用户去 `dev.sankuai.com/code/home` 或对应仓库详情页发起权限申请；如果已知仓库地址，给出对应 `repo-detail` 链接并建议申请“普通成员及以上”权限
- 如果健康检查端口已被占用，启动前就要直接失败并提示用户处理

## 常用参数

- `--repo <path>`: 目标项目根目录
- `--host-env <env>`: 默认 `test`
- `--target-home <path>`: 把用户目录重定向到测试目录；仅在测试 skill 时使用
- `--install-root <path>`: 自定义用户级工具安装目录
- `--shell-rc <path>`: 指定写入的 shell 启动文件
- `--write-shell-rc`: 显式允许修改 shell 启动文件
- `--force-install`: 即使本机已有环境，也强制生成并使用 skill 管理目录的环境
- `--skip-build`: 启动时跳过预编译
- `--foreground`: 前台启动
- `--no-download`: 缺工具时不自动下载，只做检测和报错

## 给用户的输出模板

当用户问“环境搭好了没”时，优先回答：

- 目标项目：`<repo>`
- JDK 要求：`8`（固定）
- Maven 要求：`<version>`
- 发布模块：`<pub_module>`
- 启动类：`<main_class>`
- AppKey：`<appkey or 待补充>`
- 健康地址：`<test_url>`
- 用户级安装目录：`~/.hotel-trade/backend-env`
- Maven 仓库：`~/.m2/repository`
- shell 配置文件：默认不改；如需修改则为 `~/.zshrc`
- appenv 状态：`<ok / missing / misconfigured>`
- 如 appenv 缺失：参考 `https://km.sankuai.com/collabpage/2712812595` 手动配置
- 下一步命令：`setup` / `prepare` / `start`
- 如无仓库权限：前往对应仓库详情页或 `https://dev.sankuai.com/code/home` 发起权限申请
