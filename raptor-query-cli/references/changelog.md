# Changelog — raptor-query-cli（历史版本）

- **v1.11.1** (2026-06-01)：
  - `topo-api`/`topology`/`rpc`/`sets`：修复 `--json` 输出忽略用户过滤参数的问题（如 `-d`、`--sort`、`-l`、`--target`、`--group` 等传了但 JSON 中未体现）
  - `host-metrics`：`-m` 支持含 tag 的指标名（如 `df.bytes.free.percent/fstype=ext4,mount=/opt`），tag 中的逗号不再被误当作多指标分隔符；支持多次 `-m` 传入

- **v1.11.0** (2026-05-29)：
  - `rpc`：新增 `--target`/`--target-method` 过滤指定服务和方法；新增 `--expand`/`--expand-all` 展开明细；默认排序改为 `failrate`；输出新增 `timeout` 列并修复 `fail%` 显示偏小问题

- **v1.10.10** (2026-05-28)：限流自动退避重试（最多 3 次，指数退避 + 随机抖动）；网络抖动额外重试 1 次；限流耗尽后按 token 来源给出差异化提示

- **v1.10.9** (2026-05-06)：`types`/`names` 输出不再截断，全量展示；`names` 查询性能优化；限流报错提示更明确

- **v1.10.8** (2026-05-06)：`logview-detail` 错误堆栈全量输出，不再截断

- **v1.10.7** (2026-04-27)：
  - `transaction`/`event`/`problem`：`-i/--ip` 支持逗号分隔多个 IP，结果按 `ip/type/name` 维度汇总展示
  - 所有命令：`--json` 模式下错误信息改走 stderr（不再污染 stdout JSON 输出）；JSON 输出中文不再转义为 `\uXXXX`

- **v1.10.6** (2026-04-27)：修复文档中示例命令未同步更新为 `raptor-prod` 的问题

- **v1.10.5** (2026-04-27)：入口命令从 `raptor` 改为 `raptor-prod`；版本号动态读取，不再硬编码

- **v1.10.4** (2026-04-27)：内部维护（安全扫描豁免标注）

- **v1.10.3** (2026-04-22)：修复 `offline-stat --list` 展示格式问题（type 含方括号时用户复制值查不到数据）

- **v1.10.2** (2026-04-22)：修复绝对时间结束值在 59 秒/59 分时进位遗漏的问题

- **v1.10.1** (2026-04-22)：文档瘦身优化

- **v1.10.0** (2026-04-22)：
  - `trace`：新增全量查询模式（不传 `-a` 即可查全量 span）
  - 时间粒度自动推断增强（新增 second/week/month 粒度，支持整月/周/天/小时对齐检测）
  - 时间参数支持更多格式（`20260406`、`202604061357` 等紧凑格式）

- **v1.9.16** (2026-04-21)：补齐 `topology`/`topo-api`/`logview`/`logview-detail`/`sets`/`names` 参数文档；`offline-stat` 参数文档独立；新增 `--end` 参数说明

- **v1.9.15** (2026-04-21)：
  - 新增 `offline-stat`（别名 `ofs`）命令，支持按 Appkey 请求量/成功率排行查询
  - `--list` 模式列出所有可查 type × name 组合
  - 支持参数：`-t type`、`-n name`、`-a appkey`（可选过滤）、`-c category`、`-s start`、`--sort`、`--json`

- **v1.9.14** (2026-04-16)：修复 `logview-detail`、`business`、`trace` 命令渲染时间戳时报错的问题

- **v1.9.13** (2026-04-15)：
  - 新增 `sets` 命令，查看机器分组列表（set/machine/custom/region）；`--group <名>` 列出该分组下的机器
  - `-i/--ip` 参数 help 说明更新，明确支持 set 名（如 `gray-release-nib-st`）

- **v1.9.12** (2026-04-13)：
  - `types`/`names`/`ips`：`-s` 不再必填，默认查最近 1h
  - `event`：新增 `--trend` 参数，多 type/name 时可逐一输出时序趋势
  - 时间参数统一支持紧凑格式（`20260406135700`、`202604061357`、`20260406`）
  - 入口脚本兼容性修复（消除 `bad interpreter` 问题）

- **v1.9.8** (2026-03-23)：新增 `topo-api` 接口级拓扑命令；`topology` 修复 down 方向查询 bug，支持 `-l`/`--sort`

- **v1.9.7** (2026-03-23)：补全 `rpc`（`-l`/`--sort`）、`trace`（`--span`/`--diagnose`/`--flame`/`--json`）、`logview-detail`（`--url` 解析）文档

- **v1.9.6** (2026-03-23)：Token 改为自动获取，开箱即用；支持 `RAPTOR_API_TOKEN` 环境变量覆盖

- **v1.9.5** (2026-03-20)：入口脚本兼容任意工作目录

- **v1.9.2** (2026-03-16)：完善命令别名（`biz`/`topo`/`hm`/`ld`）
