---
name: mdp-ai-sdlc-env-install
description: 检测美团研发环境工具链是否安装，并自动安装缺失工具。包括 Catpaw CLI、mtskills、oa-skills citadel、mdp spec kit、ones-cli 以及 AI-SDLC Local Agent。

metadata:
  skillhub.creator: "xiejian07"
  skillhub.updater: "yanjiang"
  skillhub.version: "V7"
  skillhub.source: "FRIDAY Skillhub"
  skillhub.skill_id: "15018"
  skillhub.high_sensitive: "false"
---

# 研发环境检测与自动安装 Skill

按顺序执行以下 6 个步骤，发现未安装则立即自动安装，安装完成后重新验证：

| 步骤 | 工具/任务 | 检测命令 | 说明 |
|------|-----------|----------|------|
| 1 | Catpaw CLI + Claude Code | `mc -v` | 必须最先检测，后续工具依赖它 |
| 2 | mtskills | `mtskills -V` | 美团技能包管理工具 |
| 3 | oa-skills citadel | `oa-skills citadel listTools` | 美团内部 skill，需要本地 SSO |
| 4 | mdp spec kit | `mdp_specify version \| grep 'Template Version'` | MDP 规范工具 |
| 5 | ones-cli | `which ones` | Ones工具 |
| 6 | tmux | `tmux -V` | 终端复用工具 |
| 7 | AI-SDLC Local Agent | `./agent.sh start` | AI-SDLC 与本地环境的桥接服务 |

---

## 执行原则

- 每一步：先检测 → 未安装则自动执行安装命令 → 安装后重新验证
- 实时告知用户当前正在做什么（检测中 / 安装中 / 验证中）
- Catpaw CLI 安装时同步安装 Claude Code

---

## 第一步：Catpaw CLI 和 Claude Code

**检测Catpaw CLI：**
```bash
mc -v
```
**检测Claude Code：**
```bash
claude -p -v
```

- 判断输出含 `command not found` 或为空 → 未安装
- 否则已安装，从输出中提取版本号展示

**未安装，征询用户同意后安装（按顺序执行）：**

第一步，安装 Catpaw CLI：
```bash
bash -c "$(curl -sL https://s3plus.sankuai.com/mcopilot-cli/install.sh)"
```
> 如果提示 `/usr/local/bin/mc: Permission denied`，改用 sudo 执行：
> ```bash
> sudo bash -c "$(curl -sL https://s3plus.sankuai.com/mcopilot-cli/install.sh)"
> ```

第二步，安装 Claude Code（优先用 npm 方式，Node.js >= 18）：
```bash
npm install -g @anthropic-ai/claude-code
```
> 如果网络可访问 claude.ai，也可用：
> ```bash
> curl -fsSL https://claude.ai/install.sh | bash
> ```

安装后重新执行 `mc -v` 和 `claude -p -v` 验证。

---

## 第二步：mtskills

**检测：**
```bash
mtskills -V
```

- 输出含 `command not found` 或为空 → 未安装
- 否则已安装，从输出中提取版本号展示

**未安装，自动安装：**
```bash
npm i -g @mtfe/mtskills --registry=http://r.npm.sankuai.com
```

> 需要 Node.js >= 20，安装前先确认：`node --version`

安装后重新执行 `mtskills -V` 验证。

---

## 第三步：oa-skills citadel

**检测：**（超时时间 15 秒，因为需要 SSO 认证）
```bash
oa-skills citadel listTools
```

- 输出含 `command not found` → oa-skills 未安装，执行安装
- 命令正常返回工具列表 → 已安装且已认证，✅ 完成
- 超时或输出含认证失败关键词（`auth`、`token`、`unauthorized`、`login`）→ 已安装但 SSO 未认证，进入**自动诊断与修复流程**

**未安装，自动安装（两步）：**

第一步，安装 oa-skills CLI：
```bash
npm install -g @it/oa-skills@latest --registry=http://r.npm.sankuai.com
```

第二步，通过 mtskills 安装 citadel skill 到全局：
```bash
mtskills i citadel --global -y
```

安装完成后，同样进入下方的**自动诊断与修复流程**完成认证。

---

### SSO 未认证时的处理流程

**Step 1：更新 oa-skills citadel 到最新版：**
```bash
npm install -g @it/oa-skills@latest --registry=http://r.npm.sankuai.com
mtskills i citadel --global -y
```

**Step 2：询问用户 MIS 号，并写入配置：**

1. 询问用户的 MIS 号（美团工号，如 `zhangsan`）
2. 自动写入配置文件：
```bash
mkdir -p ~/.config
cat > ~/.config/clawdgw.json << 'EOF'
{
  "defaultUserId": "YOUR_MIS"
}
EOF
```
（将 `YOUR_MIS` 替换为用户实际 MIS 号）

**Step 3：触发 CIBA 认证，等待用户在大象 App 确认：**

```bash
oa-skills citadel listTools
```

告知用户：「正在触发 SSO CIBA 认证，请打开大象 App，在「待办」或「消息」中找到认证请求并点击确认。」

每隔 10 秒重试一次，最多等待 120 秒（12 次），期间持续告知用户等待状态。成功返回工具列表即认证完成。

---

## 第四步：mdp spec kit

**检测：**
```bash
mdp_specify version | grep 'Template Version'
```

- 输出非空 → 已安装
- 输出为空 → 未安装

**未安装，自动安装：**

```bash
uv tool install mdp-specify-cli --from git+ssh://git.sankuai.com/hbar/mdp-spec.git --reinstall
```

> 依赖 `uv`，如果提示找不到命令，先安装 uv：
> ```bash
> curl -LsSf https://astral.sh/uv/install.sh | sh
> ```
> 安装 uv 后重新执行上面的安装命令。

安装后执行 `mdp_specify version | grep 'Template Version'` 验证。

---

## 第五步：Ones-CLI

**检测：** 检查 ones-cli 是否已安装及已登录。
```bash
which ones
```

- 若命令不存在，先执行安装后再继续：
bash         npm install -g @ee/ones-cli --registry=http://r.npm.sankuai.com         
- 检查登录状态：
bash         ones sso status         
- 若显示未登录，执行登录后再继续：
bash         ones sso login --browser -f      


---

修改后的内容如下：

---

## 第六步：tmux

**检测：**

```bash
tmux -V
```

输出含 command not found → 未安装
否则已安装，从输出中提取版本号展示

未安装，自动安装：

```bash
brew install tmux
```

安装后重新执行 tmux -V 验证。

---

## 第七步：AI-SDLC Local Agent

**检测：** 检查 `~/ai-dlc-agent` 目录是否存在，以及 agent 进程是否运行中。

**未安装，自动安装并启动：**

第一步，克隆仓库：

```bash
git clone ssh://git@git.sankuai.com/hbar/ai-dlc-agent.git ~/ai-dlc-agent
```

第二步，安装依赖：

```bash
cd ~/ai-dlc-agent && pip install -r requirements.txt
```

> macOS 不允许往系统 Python 装包，如提示权限问题，使用虚拟环境：
>
> ```bash
> cd ~/ai-dlc-agent && python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
> ```

第三步，启动 Agent：

* **未使用项目虚拟 Python 环境：**

  ```bash
  cd ~/ai-dlc-agent && ./agent.sh start
  ```
* **使用虚拟环境：**

  ```bash
  cd ~/ai-dlc-agent && source .venv/bin/activate && ./agent.sh start
  ```

**已安装但未运行时：** 直接执行启动命令：

* **未使用项目虚拟 Python 环境：**

  ```bash
  cd ~/ai-dlc-agent && ./agent.sh start
  ```
* **使用虚拟环境：**

  ```bash
  cd ~/ai-dlc-agent && source .venv/bin/activate && ./agent.sh start
  ```

启动后访问 AI-SDLC 管理平台完成环境配置：[https://mdp.sankuai.com/aidlc](https://mdp.sankuai.com/aidlc)

> 查看日志：`tail -f ~/ai-dlc-agent/data/logs/agent.log`
> 重启 Agent：`cd ~/ai-dlc-agent && ./agent.sh restart`

---

## 结果汇总格式

全部检测/安装完成后，以表格形式汇总：

```
## 研发环境检测结果

| 工具 | 状态 | 说明 |
|------|------|------|
| Catpaw CLI | ✅ 已安装 | 版本 x.x.x |
| Claude Code | ✅ 已安装（自动安装） | - |
| mtskills    | ✅ 已安装（自动安装） | 版本 x.x.x |
| oa-skills citadel | ✅ 已安装 | - |
| mdp spec kit | ✅ 已安装（自动安装） | - |
| ones-cli | ✅ 已安装 | - |
| tmux | ✅ 已安装 | 版本 x.x.x |
| AI-SDLC Local Agent | ✅ 已启动 | 管理平台：https://mdp.sankuai.com/aidlc |
```

---

## 常见问题

**Q: oa-skills citadel listTools 超时或认证失败**
A: SSO 登录态未认证。Skill 会自动询问 MIS 号并写入 `~/.config/clawdgw.json`，然后触发 CIBA 认证——打开大象 App，在「待办」或「消息」中找到认证请求并点击确认即可。

**Q: npm 安装失败，提示 registry 连接超时**
A: 需要在美团内网环境下执行，确认网络连接后重试。

**Q: 安装完成但命令还是找不到**
A: npm 全局安装目录可能不在 PATH 中，执行 `npm root -g` 查看安装路径，确认该路径已加入 PATH。

