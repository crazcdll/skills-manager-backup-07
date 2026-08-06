# 回溯追踪算法详细设计

## 核心思想

AI-CR 标注的代码行若被开发者后续修改，说明 AI 发现了真问题（隐式采纳）。
但需要处理行号漂移、噪声 commit 等干扰，才能得到可靠的 Ground Truth。

## 算法输入

```
input:
  merge_sha: string          # PR 的 merge commit SHA
  repo_url: string           # 仓库地址
  annotations: [             # AI-CR 的检出项列表
    {
      file: string,          # 文件路径
      line_range: [int, int],# 标注行范围 [start, end]
      severity: string,      # P0/P1/P2/P3
      description: string    # 问题描述
    }
  ]
  window_days: 30            # 观察窗口（天）
```

## 算法步骤

### Step 1: 获取后续 commit 序列

```bash
# Shallow clone 足够（只需 merge 后的历史）
git clone --depth 200 --single-branch --branch main <repo_url> /tmp/eval-repo

# 获取 merge 后 30 天内的 commit（只看主分支）
git log --after="<merge_date>" --before="<merge_date + 30d>" \
  --format="%H %an %ai %s" --first-parent main > commits.txt
```

输出：时间顺序的 commit 列表（SHA, author, date, message）

### Step 2: 行号映射（Line Tracking）

**问题**：merge 后如果有人在标注行之前插入/删除代码，标注行的"当前行号"会偏移。

**算法**：逐 commit 累积偏移量

```python
def track_line_range(file_path, original_range, commits):
    """追踪一个行范围在后续 commit 中的位置变化"""
    current_start, current_end = original_range
    
    for commit in commits:
        diff = git_diff(commit.parent, commit, file_path)
        if diff is None:
            continue  # 该 commit 没修改这个文件
        
        offset = 0
        for hunk in diff.hunks:
            # hunk: @@ -old_start,old_count +new_start,new_count @@
            if hunk.old_start < current_start:
                # 在标注行之前的修改，计算偏移
                offset += hunk.new_count - hunk.old_count
            elif hunk.old_start <= current_end:
                # 与标注行有交集！这是一次"命中"
                return {
                    "hit": True,
                    "commit": commit,
                    "overlap_lines": calculate_overlap(hunk, current_start, current_end)
                }
        
        # 应用偏移
        current_start += offset
        current_end += offset
    
    return {"hit": False}
```

**边界处理**：
- 文件被删除 → verdict = "file_deleted"（不计入评测）
- 文件被重命名 → 用 `git log --follow` 追踪新路径
- 标注行被完全删除（非替换）→ 视为"命中"（可能是移除有问题的代码）

### Step 3: 修改检测与交集计算

```python
def calculate_overlap(hunk, anno_start, anno_end):
    """计算 hunk 修改范围与标注范围的重叠度"""
    hunk_start = hunk.old_start
    hunk_end = hunk.old_start + hunk.old_count - 1
    
    overlap_start = max(hunk_start, anno_start)
    overlap_end = min(hunk_end, anno_end)
    
    if overlap_start > overlap_end:
        return 0.0
    
    overlap_lines = overlap_end - overlap_start + 1
    anno_lines = anno_end - anno_start + 1
    
    return overlap_lines / anno_lines  # overlap_ratio: 0.0 ~ 1.0
```

**判定标准**：
- overlap_ratio ≥ 0.5 → 确认命中
- overlap_ratio 0.2~0.5 → 疑似命中，需结合其他信号
- overlap_ratio < 0.2 → 不算命中（可能是附近的无关修改）

### Step 4: 噪声过滤

以下情况虽然"命中"了标注行，但不应视为"采纳修复"：

| 噪声类型 | 检测方法 | 处理 |
|---------|---------|------|
| 纯格式化 | commit message ∈ {format, style, lint, prettier, checkstyle} 且 diff 无语义变更（只有空白/换行变化） | 跳过此 commit |
| 批量重构 | 单 commit 修改文件数 > 50 | 降权（confidence × 0.3） |
| Revert | commit message startswith "Revert" 或 "revert:" | 跳过 |
| 依赖升级 | 只修改 pom.xml / build.gradle / package.json | 跳过 |
| 自动生成 | 文件路径包含 generated / auto-gen / target/ | 跳过 |

**语义变更检测**（用于区分格式化 vs 真修改）：

```bash
# 去除空白后对比
git diff --ignore-all-space <parent> <commit> -- <file> | wc -l
# 如果去空白后 diff 为 0 → 纯格式化
```

### Step 5: 置信度评分模型

```python
def calculate_confidence(annotation, hit_result, explicit_feedback):
    """
    综合多维信号计算最终置信度
    """
    # === 基础分 (base_score) ===
    if explicit_feedback == "✅已采纳":
        base = 1.0
    elif explicit_feedback == "❌误报":
        return 0.0  # 直接判定为反例
    elif hit_result.hit:
        if hit_result.commit.author == annotation.pr_submitter:
            # 自己修自己的 → 高置信
            base = 0.85
        elif has_fix_keywords(hit_result.commit.message):
            # commit message 含修复关键词
            base = 0.80
        elif hit_result.overlap_ratio >= 0.8:
            # 精确命中但无关键词
            base = 0.75
        else:
            # 部分命中
            base = 0.60
    else:
        # 未命中：可能误报，也可能暂不修复
        if explicit_feedback == "⏭暂不修复":
            base = 0.40  # 不确定
        else:
            base = 0.25  # 倾向误报
    
    # === 信号增强 (signal_boost) ===
    boost = 1.0
    if annotation.severity == "P0" and hit_result.hit:
        boost *= 1.15  # P0 被修复 → 高价值样本
    if has_test_added(hit_result.commit):
        boost *= 1.10  # 配套加了测试 → 高确定性
    if hit_result.overlap_ratio >= 0.9:
        boost *= 1.05  # 精确命中
    
    # === 时效衰减 (freshness_decay) ===
    days_since_merge = (hit_result.commit.date - annotation.merge_date).days
    if days_since_merge <= 7:
        decay = 1.0
    elif days_since_merge <= 14:
        decay = 0.9
    elif days_since_merge <= 30:
        decay = 0.8
    else:
        decay = 0.6
    
    # === 最终置信度 ===
    confidence = min(base * boost * decay, 1.0)
    return round(confidence, 3)


def has_fix_keywords(message):
    """检测 commit message 是否包含修复关键词"""
    keywords = [
        "fix", "bug", "repair", "resolve", "patch",
        "修复", "修正", "解决", "NPE", "空指针",
        "hotfix", "bugfix", "issue"
    ]
    msg_lower = message.lower()
    return any(kw in msg_lower for kw in keywords)


def has_test_added(commit):
    """检测 commit 是否新增了测试文件"""
    for file in commit.changed_files:
        if "test" in file.lower() or "Test" in file:
            if commit.file_status(file) == "added":
                return True
    return False
```

### Step 6: Verdict 判定

```python
def determine_verdict(confidence):
    if confidence >= 0.8:
        return "accepted"        # 确认采纳，直接入评测集
    elif confidence >= 0.6:
        return "likely_accepted" # 大概率采纳，低优先级 review
    elif confidence >= 0.4:
        return "uncertain"       # 不确定，需人工仲裁
    elif confidence > 0.0:
        return "likely_fp"       # 大概率误报，可入反例库
    else:
        return "confirmed_fp"    # 确认误报（显式 ❌标记）
```

## 性能优化

| 优化点 | 方法 |
|--------|------|
| 减少 clone | 同仓库多个 PR 共享一次 clone |
| 浅克隆 | `--depth 200` 足够覆盖 30 天历史 |
| 文件级过滤 | `git log -- <file>` 只查标注文件的历史 |
| 并行处理 | 不同仓库的 PR 可并发执行 |
| 缓存结果 | 已验证的 PR 结果缓存到 `eval-dataset/.cache/` |

## 限制与已知问题

1. **Squash merge 丢失细粒度历史**：如果 PR 是 squash merge，后续 fix 如果也被 squash，可能丢失行级追踪信息
2. **跨分支修复**：fix 在其他分支提交后才合入 main，日期可能超出窗口
3. **间接修复**：重构后问题不存在了（如整个方法重写），但行号追踪认为"未命中"
4. **无法测 Recall**：回溯法只能验证"报了的对不对"（Precision），无法测"漏了多少"
