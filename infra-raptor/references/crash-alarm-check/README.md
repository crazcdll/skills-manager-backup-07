# crash-alarm-check

> Crash 告警排查与根因分析助手——把告警消息发给我，自动拉堆栈、分析根因、给出结论

**版本：** v1.5.5 | **作者：** nieyunlong

---

## 功能概览

收到任何 Crash 告警后，自动完成：

1. **解析告警** — 提取时间范围、组件、告警等级
2. **拉取完整堆栈** — 通过 crash-mcp-server 获取 androidLog
3. **根因分析** — 识别异常类型、还原触发路径、定位责任模块
4. **输出结论** — 标准化分析报告 + 可操作建议

---

## 支持场景

- 新增异常告警（P1/P2/P3）
- Crash 数量激增告警
- 版本劣化告警
- 特定组件异常查询
- 指定时间段 crash 排查

---

## 快速开始

直接把告警消息粘贴发给我即可，无需任何额外操作。

---

## 快速开始（新用户）

1. 解压 zip 到 `~/.openclaw/skills/crash-alarm-check/`
2. 直接使用——首次运行时脚本会自动提示输入 mis：
   ```
   [crash-alarm-check] 首次使用，需要配置你的 mis 账号。
   请输入你的 mis（如 zhangsan）：
   ```
3. 输入后自动保存配置，之后无感知复用

## 前置依赖

### crash-mcp-server（无需鉴权，自动注册）

依赖 [crash详细日志 MCP（Friday id=1176）](https://friday.sankuai.com/mcp/mcp-server-detail?activeTab=overview&id=1176)，接入点无需 token。

首次使用时手动注册（或由 skill 自动完成）：

```bash
mcporter config add crash-mcp-server http://mcphub-server.sankuai.com/mcphub-api/0fbcecb097ec48 --allow-http
```

---

## 输出格式

每次分析包含以下所有部分：

```
{策略名称} Crash 根因分析

异常类型：...
完整异常：...
崩溃 UUID：...
设备 ID：...

根因分析：...

触发路径：...

关键信息：版本 / 组件 / 触发场景 / 进程

---
✅ 结论：[需要修复 / 建议暂不修复 / 建议忽略]
（含影响范围 / 可操作性评估 / 具体建议）
```

---

## 支持平台

| App | project |
|---|---|
| 美团 Android | android_platform_monitor |
| 美团 iOS | meituan |
| 点评 Android | android-nova |
| 点评 iOS | nova |
| 鸿蒙美团 | meituan-harmony |

---

## 目录结构

```
crash-alarm-check/
├── SKILL.md          # skill 主配置（供 OpenClaw 读取）
├── README.md         # 本文件
├── CHANGELOG.md      # 版本历史
└── scripts/          # 辅助脚本
```

---

## 版本历史

详见 CHANGELOG.md

- v1.5.5：mis 自动从 sso-auth-cli cache.json 读取，与 component-crash-chart 对齐
- v1.5.4：修复 sso-auth-cli 换票 stdout 为空，改用 --cookie 模式
- v1.5.0：换票配置抽为 config.json，补端到端示例，iOS字段名说明
- v1.4.1：补充触发边界 + Token 文件权限加固
- v1.4.0：SKILL.md 精简 + 换票脚本化
- v1.3.2：换票升级为三级 fallback，支持 CIBA 大象授权 + cache.json 兜底
- v1.3.1：sso-auth-cli 自动安装
- v1.3.0：换票改用 sso-auth-cli，Token 缓存延长至 3 天
- v1.2.0：换票改为 app 模式，解决卡死问题
- v1.0.0：初始版本

---

## 常见问题

Q: 堆栈拉不到？
A: 检查告警时间范围是否正确，部分 crash 可能上报延迟，可适当扩大查询时间窗口。

Q: 支持 iOS / 鸿蒙吗？
A: 支持，project 传对应值即可（见上方平台映射表）。
