# Ground Truth Schema

## 评测集 JSON 完整 Schema

### 顶层结构

```json
{
  "schema_version": "2.0",
  "generated_at": "2026-05-10T22:00:00+08:00",
  "generator": "eval-dataset-selector v1.0",
  "statistics": {
    "total_samples": 95,
    "total_bugs": 142,
    "total_clean_zones": 67,
    "coverage_rate": 0.935,
    "avg_confidence": 0.82,
    "severity_distribution": {"P0": 28, "P1": 38, "P2": 22, "P3": 7},
    "layer_distribution": {"L1": 48, "L2": 32, "L3": 15}
  },
  "coverage_matrix": {
    "C1_L1": 7, "C1_L2": 4, "C1_L3": 2,
    "C2_L1": 5, "C2_L2": 2,
    "C3_L1": 4, "C3_L2": 6, "C3_L3": 3,
    "C4_L1": 3, "C4_L2": 1,
    "C5_L1": 3,
    "C6_L1": 4, "C6_L2": 3,
    "C7_L3": 4
  },
  "samples": [ /* Sample 对象数组 */ ]
}
```

### Sample 对象

```json
{
  "id": "L1-001",
  "pr_url": "https://dev.sankuai.com/code/repo-detail/<org>/<repo>/pr/<id>/diff",
  "merge_sha": "abc1234def5678",
  "merge_date": "2026-03-15",
  "repo": "com.sankuai.xxx.yyy",
  "submitter": "zhangsan",
  "cr_doc_id": "275xxxxx",
  "cr_doc_url": "https://km.sankuai.com/collabpage/275xxxxx",

  "bugs": [ /* Bug 对象数组 */ ],
  "clean_zones": [ /* CleanZone 对象数组 */ ],

  "metadata": {
    "selection_tier": "gold | silver | bronze",
    "selection_reason": "描述为何选入此样本",
    "confidence_avg": 0.88,
    "review_status": "auto | needs_review | verified",
    "reviewer": "mengmuzi",
    "review_date": "2026-05-15",
    "notes": "可选备注"
  }
}
```

### Bug 对象

```json
{
  "bug_id": "L1-001-B1",
  "file": "src/main/java/com/sankuai/xxx/service/OrderService.java",
  "line_range": [42, 55],
  "severity": "P0",
  "defect_class": "C1_npe",
  "context_layer_required": "L1_diff_visible",
  "trigger_type": "zero_tolerance",
  "description": "Map.get() 返回 Integer 直接拆箱，key 不存在时 NPE",

  "ground_truth_source": "explicit_accept | fix_commit | ai_detected | manual",
  "evidence": {
    "signal_type": "explicit_feedback | fix_commit | retrospective_hit",
    "feedback_mark": "✅已采纳",
    "fix_commit": "def5678abc",
    "fix_author": "zhangsan",
    "fix_date": "2026-03-17",
    "fix_message": "fix: 修复订单查询 NPE",
    "overlap_ratio": 0.85
  },
  "confidence": 0.92,
  "human_verified": true,

  "expected_detection": {
    "should_detect": true,
    "expected_severity": "P0",
    "expected_step": "Step 4B",
    "tolerance": {
      "severity_flex": 1,
      "line_range_flex": 5
    }
  }
}
```

### CleanZone 对象

```json
{
  "zone_id": "L1-001-CZ1",
  "file": "src/main/java/com/sankuai/xxx/service/SafeService.java",
  "line_range": [10, 30],
  "reason": "Optional.ofNullable 前置保护，Map.get 后有 null 检查",
  "related_defect_class": "C1_npe",
  "auto_detected": true,
  "detection_method": "同文件存在 null check pattern 保护",
  "human_verified": true
}
```

---

## 字段说明

### severity 取值

| 值 | 含义 | 评分权重 |
|----|------|---------|
| P0 | 零容忍缺陷（NPE/CME/SQL注入等，必修） | 4 |
| P1 | 稳定性安全（资源泄漏/超时/线程安全等） | 2 |
| P2 | 规范架构（编码规范/设计模式/命名等） | 1 |
| P3 | 性能建议（优化建议，非强制） | 0.5 |

### defect_class 取值

| 值 | 含义 |
|----|------|
| C1_npe | NPE / 空指针 |
| C2_resource_leak | 资源泄漏 / 超限 |
| C3_logic_error | 逻辑错误 / 条件遗漏 |
| C4_concurrency | 并发 / 线程安全 |
| C5_security | 安全 / 注入 |
| C6_performance | 性能退化 |
| C7_cross_repo | 跨仓库兼容 |

### context_layer_required 取值

| 值 | 含义 |
|----|------|
| L1_diff_visible | 仅看 diff 即可发现 |
| L2_intra_repo_search | 需仓库内搜索引用 |
| L3_cross_repo_or_business | 需跨仓库或业务语义 |

### trigger_type 取值

| 值 | 含义 |
|----|------|
| zero_tolerance | 零容忍规则 |
| stability | 稳定性安全规则 |
| coding_standard | 编码规范规则 |
| performance | 性能规则 |
| cross_repo | 跨仓库兼容规则 |

### ground_truth_source 取值

| 值 | 含义 | 可靠性 |
|----|------|--------|
| explicit_accept | 用户显式 ✅已采纳 | ⭐⭐⭐⭐⭐ |
| fix_commit | 后续 commit 修复了该问题 | ⭐⭐⭐⭐ |
| ai_detected | AI-CR 检出但无后续反馈 | ⭐⭐⭐ |
| manual | 人工标注（非 AI 检出） | ⭐⭐⭐⭐⭐ |

### review_status 取值

| 值 | 含义 |
|----|------|
| auto | 自动生成，confidence ≥ 0.8，无需 review |
| needs_review | confidence 0.5~0.8，需人工确认 |
| verified | 已经人工确认 |

---

## 评分时的匹配规则

评测执行后，Skill 输出 vs Ground Truth 的匹配逻辑：

### 正例匹配（TP 判定）

Skill 检出项与 Ground Truth bug 匹配条件（满足全部）：
1. **文件匹配**：路径后缀匹配（忽略仓库根目录前缀）
2. **行号匹配**：Skill 报出行号在 `line_range ± tolerance.line_range_flex` 范围内
3. **语义匹配**：Skill 描述的问题与 bug.description 语义一致（LLM 辅助判定）

### 误报判定（FP 判定）

Skill 检出项落在某个 CleanZone 的 `line_range` 范围内 → FP

### 漏报判定（FN 判定）

Ground Truth 中 `expected_detection.should_detect = true` 的 bug 未被 Skill 匹配到 → FN

### 评分公式

```
单样本:
  TP_weighted = Σ(匹配的 bug × severity_weight)
  FP_penalty = Σ(clean_zone 内的误报 × 0.5 + 非 clean_zone 的误报 × 0.3)
  FN_weighted = Σ(未检出的 bug × severity_weight)

全局:
  Precision = TP / (TP + FP)
  Recall = TP / (TP + FN)
  F₂ = 5 × P × R / (4P + R)
```
