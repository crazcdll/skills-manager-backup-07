# 覆盖矩阵与代表性采样

## 目标覆盖矩阵

评测集应均匀覆盖 defect_class × context_layer 矩阵的各格子。

### 最小覆盖要求（每格最少样本数）

| 缺陷类别 | L1 (Diff可见) | L2 (仓库内反查) | L3 (跨仓/业务) | 行合计 |
|---------|:---:|:---:|:---:|:---:|
| C1 NPE/空指针 | 5 | 3 | 2 | 10 |
| C2 资源泄漏/超限 | 4 | 2 | - | 6 |
| C3 逻辑错误/条件遗漏 | 3 | 5 | 3 | 11 |
| C4 并发/线程安全 | 3 | 2 | - | 5 |
| C5 安全/注入 | 3 | - | - | 3 |
| C6 性能退化 | 3 | 3 | - | 6 |
| C7 跨仓库兼容 | - | - | 5 | 5 |
| **列合计** | **21** | **15** | **10** | **46（最小）** |

> `-` 表示该组合在实际场景中极少出现，不做强制要求。
> 总目标 80~120 条，最小 46 是下限，余量用于加厚高价值格子。

### 理想分布（首期目标 100 条）

| 缺陷类别 | L1 | L2 | L3 | 行合计 |
|---------|:---:|:---:|:---:|:---:|
| C1 NPE/空指针 | 8 | 5 | 3 | 16 |
| C2 资源泄漏/超限 | 6 | 3 | - | 9 |
| C3 逻辑错误/条件遗漏 | 5 | 8 | 5 | 18 |
| C4 并发/线程安全 | 5 | 3 | - | 8 |
| C5 安全/注入 | 5 | - | - | 5 |
| C6 性能退化 | 5 | 5 | - | 10 |
| C7 跨仓库兼容 | - | - | 12 | 12 |
| **列合计** | **34** | **24** | **20** | **78** |

> 剩余 22 条预留给高价值但难分类的样本，或用于加厚实际分布中的薄弱格。

---

## 采样算法

### 贪心覆盖采样

```python
def greedy_coverage_sampling(candidates, matrix_target, max_samples=120):
    """
    从候选池中按覆盖矩阵做贪心采样
    
    candidates: 按 confidence 降序排列的候选样本列表
    matrix_target: 每个格子的目标样本数 dict
    max_samples: 最大采样数
    """
    selected = []
    matrix_current = defaultdict(int)  # 当前每格已选数量
    
    # Phase 1: 填充空白格（优先保证覆盖度）
    for candidate in candidates:
        if len(selected) >= max_samples:
            break
        
        cell = (candidate.defect_class, candidate.context_layer)
        target = matrix_target.get(cell, 0)
        
        if target == 0:
            continue  # 该组合不在目标矩阵中
        
        if matrix_current[cell] < target:
            # 该格还未填满，优先选入
            priority = target - matrix_current[cell]  # 越空越优先
            selected.append((candidate, priority))
            matrix_current[cell] += 1
    
    # Phase 2: 补充高置信度样本（提升整体质量）
    remaining_budget = max_samples - len(selected)
    for candidate in candidates:
        if remaining_budget <= 0:
            break
        if candidate not in [s[0] for s in selected]:
            if candidate.confidence >= 0.8:
                selected.append((candidate, 0))
                remaining_budget -= 1
    
    return [s[0] for s in selected]
```

### 空白格检测与告警

```python
def check_coverage(selected_samples, matrix_target):
    """检查覆盖矩阵填充情况"""
    matrix_actual = defaultdict(int)
    for sample in selected_samples:
        for bug in sample.bugs:
            cell = (bug.defect_class, bug.context_layer)
            matrix_actual[cell] += 1
    
    gaps = []
    total_cells = len(matrix_target)
    empty_cells = 0
    
    for cell, target in matrix_target.items():
        actual = matrix_actual.get(cell, 0)
        if actual == 0:
            empty_cells += 1
            gaps.append(f"❌ {cell}: 0/{target} (空白)")
        elif actual < target:
            gaps.append(f"⚠️ {cell}: {actual}/{target} (不足)")
    
    coverage_rate = 1 - (empty_cells / total_cells)
    
    return {
        "coverage_rate": coverage_rate,
        "empty_cells": empty_cells,
        "total_cells": total_cells,
        "gaps": gaps,
        "pass": coverage_rate >= 0.90  # 空白格 ≤ 10% 为通过
    }
```

---

## 采样约束

| 约束 | 规则 | 原因 |
|------|------|------|
| 单 PR 上限 | 同一 PR 最多贡献 5 个样本 | 防止被大 PR 主导 |
| 单仓库上限 | 同一仓库最多贡献 30% 总样本 | 保证仓库多样性 |
| 时间分布 | 每月至少 10% 的样本 | 防止集中在某时间段 |
| severity 分布 | P0 占 20~35%，P1 占 30~45%，P2/P3 占余量 | 对齐实际发现分布 |
| confidence 下限 | 最终入选样本 confidence ≥ 0.5 | 保证标注质量 |

---

## 覆盖报告模板

执行采样后输出的 `coverage-report.md` 格式：

```markdown
# 评测集覆盖报告

**生成时间**: 2026-05-10
**总样本数**: 95
**覆盖率**: 93.5%（空白格 2/31）

## 覆盖矩阵

| 缺陷类别 | L1 | L2 | L3 |
|---------|:---:|:---:|:---:|
| C1 NPE | 7/5 ✅ | 4/3 ✅ | 2/2 ✅ |
| C2 资源泄漏 | 5/4 ✅ | 2/2 ✅ | - |
| C3 逻辑错误 | 4/3 ✅ | 6/5 ✅ | 3/3 ✅ |
| C4 并发 | 3/3 ✅ | 1/2 ⚠️ | - |
| C5 安全 | 3/3 ✅ | - | - |
| C6 性能 | 4/3 ✅ | 3/3 ✅ | - |
| C7 跨仓 | - | - | 4/5 ⚠️ |

## 薄弱环节

- C4_L2（并发+仓库反查）：缺 1 条，建议定向筛选
- C7_L3（跨仓兼容）：缺 1 条，建议从多仓 CR 记录中补充

## 统计分布

- Severity: P0=28(29%), P1=38(40%), P2=22(23%), P3=7(8%)
- Confidence: ≥0.9=45, 0.8~0.9=28, 0.7~0.8=15, 0.5~0.7=7
- 仓库分布: 18 个不同仓库
- 时间跨度: 2026-01 ~ 2026-05
```
