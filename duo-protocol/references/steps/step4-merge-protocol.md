# Step 4 — 生成 protocol.json（按需执行）

> **阻塞级别**：🟢 不阻塞（按需执行，与 Step 5 互斥）

## 触发条件

下游（fe-rd-agent / 用户）需要一个完整的 `protocol.json` 单文件时执行。

> ⚠️ Step 4 和 Step 5 是互斥的可选路径，不是串行步骤。根据下游需要选择执行其中一个。

## 输入

Step 3 生成的拆分子文件。

## 过程

在逐文件覆盖完成后，使用 `splits.js` 反向合并或手动组装，生成完整的 `protocol.json`。

```bash
node scripts/splits.js --reverse --input ./food-duo/{page}/ --output ./food-duo/{page}/protocol.json
```

## 输出

- `protocol.json`（完整单文件）

> ⚠️ protocol.json 内容必须与所有拆分文件完全一致。
