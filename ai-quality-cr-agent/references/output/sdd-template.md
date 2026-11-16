# SDD 校验文件格式模板（Step 3D 专用）

> Step 3D 完成后，主 Agent 将 SDD 校验汇总写入 `/tmp/cr_sdd_{prId}.md`，供 Step 7 通过 `--sdd-file` 透传给 `publish_results.py`。

---

## 有 spec 时（has_spec=true）

```markdown
### 产物完备性

- **{module}**：specs/{module}/design.md（{N}行） — ✅ 完备 / ⚠️ 简略 / ❌ 缺失

### 文码一致性

- **SDD-1** [{级别}]：{spec文件} L{行号} — spec 描述「{spec描述}」，代码实现「{代码实现}」。建议：{建议}

### 综述与建议

- **完备度**：{COMPLETE / PARTIAL(缺N个) / MISSING}
- **一致率**：约 {X}%（{N} 处不一致）
- **建议**：{自然语言综述}
```

## 无 spec 时（has_spec=false / skipped=true）

写一个简短文件，内容为「本次变更未采用 SDD，无设计产物」（或整文件留空）。Step 7 仍传 `--sdd-file`，脚本会据此在文档中体现。
