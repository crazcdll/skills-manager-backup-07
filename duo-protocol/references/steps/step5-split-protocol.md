# Step 5 — 拆分协议文件（按需执行）

> **阻塞级别**：🟢 不阻塞（按需执行，与 Step 4 互斥）

## 触发条件

输入是一个完整的 `protocol.json` 单文件、需要拆分为子文件时执行（典型场景：从平台导出的协议文件需要拆分入库）。

如果 Step 3 已直接生成拆分子文件，则无需执行本步骤。

## 输入

`protocol.json` 单文件。

## 过程

拆分为 **7 个必选文件 + 若干可选文件**：

```
.
├── componentsMap.json                         # 物料注册表（必选）
├── constData.groovy                           # 页面常量（必选）
├── dataSourceMap.groovy                       # 数据源配置（必选）
├── dependencies.json                          # 依赖声明（必选）
├── logics.groovy                              # 页面逻辑（必选）
├── pageBuildConfig.json                       # 页面构建配置（必选）
├── struct.groovy                              # 组件树结构（必选）
├── ohDependencies.json                        # 鸿蒙专属依赖声明（可选）
├── scripts/                                   # 页面脚本（可选）
│   ├── buildCustom.js                         # 构建定制脚本
│   ├── mrnConfigCustom.js                     # MRN 容器配置
│   └── firstScreenModulePaths.json            # 首屏模块路径
└── nodes/                                     # 节点独立拆分（可选）
    └── {NodeName}.groovy                      # 仅当 buildConfig.splitFile=true
```

执行拆分命令：

```bash
node scripts/splits.js --input ./food-duo/{page-name}/protocol.json --output ./food-duo/{page-name}/
```

## 输出

- 拆分后的子文件集合

> ⚠️ 拆分后必须逐文件检查，确保拆分结果与 protocol.json 完全一致。拆分只是格式转换，不是重新编码。
