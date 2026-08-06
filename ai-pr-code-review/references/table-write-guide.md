# 多维表格写入指南（Step 9）

## 表格信息

- 默认 TABLE_ID：`2751197605`
- 父文档 contentId：`2751017775`
- 学城链接：https://km.sankuai.com/xtable/2751017775

## 写入命令

每次写入前先调 `getTableMeta` 刷新 schema（用列名匹配，防顺序变化）：

> 🚨 **日期时间戳强制执行规则（违反则本次写入无效）**：
> 1. **必须先执行以下 exec 命令获取时间戳**，禁止 AI 自己推算、硬编码任何数字
> 2. 执行后必须在对话中输出结果供人工校验
> 3. 校验规则：结果必须是 13 位整数，且 > 1735660800000（2026-01-01），否则说明系统时间或命令有误，禁止继续写入

**Step 9 第一步：强制执行获取时间戳（不得跳过）**

```bash
DATE_MS=$(python3 -c "import datetime; print(int(datetime.datetime.now().replace(hour=0,minute=0,second=0,microsecond=0).timestamp()*1000))")
echo "📅 今日毫秒时间戳: $DATE_MS"
# 校验：必须是 13 位且 > 1735660800000
python3 -c "
ts = $DATE_MS
assert len(str(ts)) == 13, f'❌ 时间戳位数错误: {ts}'
assert ts > 1735660800000, f'❌ 时间戳异常，年份早于2026: {ts}'
import datetime; d = datetime.datetime.fromtimestamp(ts/1000)
print(f'✅ 校验通过，对应日期: {d.strftime(\"%Y/%m/%d\")}')
"
```

输出示例（必须在对话中可见）：
```
📅 今日毫秒时间戳: 1743379200000
✅ 校验通过，对应日期: 2026/03/31
```

**Step 9 第二步：用 $DATE_MS 写入（禁止替换成其他值）**

```bash
oa-skills citadel-database addData \
  --tableId "$TABLE_ID" --columnIds "<从getTableMeta获取>" --mis {operator_mis} \
  --data '[[$DATE_MS,"{prUrl}","{org}/{repo}","{prTitle}","{userMis}","{orgId}","{conclusion}",{p0Count},{p1Count},"{kmUrl}","{remark}"]]'
```

> ⚠️ MCM关联字段已移除（系统层面无法自动获取），表格中对应列留空，不传入 data。

## 结论字段强制映射

必须从下表选一，禁止自由发挥（确保过滤/统计一致性）：

| 3F 判定 | 写入值（原样复制，含 emoji） |
|---------|---------------------------|
| P0=0 且 P1=0 且 P2≤3 | `✅通过` |
| P0=0 且 P1=0 且 P2>3 | `💚通过有建议` |
| P0>0 或 P1>0 或 Cross-Repo P1 | `🟠需修复` |
| 架构级问题 | `🔴需重新设计` |

禁止写入「建议修改」「有问题」「通过（有建议）」等其他文字。

> 🚨 **结论字段断言（违反则写入无效，表格会显示数字而非结论文字）**：
> - ✅ **正确**：`"conclusion"` 字段传 **label 文字字符串**，如 `"🟠需修复"`
> - ❌ **错误示例（禁止）**：传 optionId 数字（如 `2750519644`）→ 表格会显示该数字而非结论文字
> - ❌ **错误示例（禁止）**：传整数序号（如 `0`, `1`, `2`, `3`）→ 表格显示序号
> - **写入前必须验证**：`conclusion` 变量赋值后断言 `isinstance(conclusion, str) and conclusion.startswith(("✅", "💚", "🟠", "🔴"))`，不满足则停止写入并报错

## 其他规则

- **组织架构（填 orgId）**：
  - ✅ 必须使用 Step 2 调用 `get_org_info.py` 返回的 `orgId` 字段（纯数字，如 `103461`）
  - ❌ **严禁填组织架构名称、部门路径、mis 号或任何推测的部门名**
  - 接口需重试 3 次（每次间隔 1s），3 次均失败时兜底填空字符串
- **多仓库**：每个 PR 各写一条，备注填「多仓库联合CR，关联PR：{其他PR链接}」
- ⚠️ **严禁 deleteData / updateData，只允许 addData 追加**
