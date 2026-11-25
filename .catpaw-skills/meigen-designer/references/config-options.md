# content.config 可选参数

V3 send 接口的 `content.config` 字段支持以下可选参数：

---

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `openSearch` | `bool` | `false` | 是否启用联网搜索 |
| `fastModel` | `str \| None` | `null` | 省略时使用完整设计师 Agent。仅在任务简单且用户明确指定模型时填写，启用轻量快速版。见[模型列表](../SKILL.md#调用)。 |
| `skill` | `str \| None` | `null` | Skill 标识 |
| `ratio` | `str \| None` | `null` | 宽高比（如 `"1:1"`, `"16:9"`） |
| `width` | `int \| None` | `null` | 宽度（像素） |
| `height` | `int \| None` | `null` | 高度（像素） |
| `promptType` | `str \| None` | `null` | 提示词类型 |

---

## 使用示例

> 凭证由脚本内部 `meigen status --json` 获取，不作为参数传入。流式执行，逐行按 `_action` 分发（见 SKILL.md）。

### 指定宽高比

```bash
python3 "$SCRIPT_DIR/generate.py" "赛博朋克城市" --config '{"ratio": "16:9"}' 2>&1
```

### 指定尺寸

```bash
python3 "$SCRIPT_DIR/generate.py" "海报设计" --config '{"width": 1024, "height": 768}' 2>&1
```

### 启用联网搜索

```bash
python3 "$SCRIPT_DIR/generate.py" "2024年最新设计趋势的海报" --config '{"openSearch": true}' 2>&1
```

### 使用快速模型

```bash
python3 "$SCRIPT_DIR/generate.py" "用 GPT-image-2.5 Flare 画一个简单图标" --model "gpt-image-2.5-flare" 2>&1
```
