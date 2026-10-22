---
ruleType: Model Request
description: 初始化集合/写List/Map/Set操作时读我。强制集合初始化容量预估(已知大小预设初始容量)、空集合返回Collections.emptyList()非null。new ArrayList/HashMap时读我。
category: Java编码规范
priority: medium
---

# Java集合处理规范

## 一、说明

本规范详细描述了Java编码规范中的集合处理要求。集合是Java编程中最常用的数据结构，正确使用集合能够提高代码质量和性能。

## 二、规则内容

### N005 [推荐] 集合初始化的规范

若对集合容量有预估，则初始化时指定初始容量大小，避免随着元素增加反复调用resize()扩容，影响性能。

**说明**：使用HashMap时可以调用构造方法HashMap(int initialCapacity)进行初始化，initialCapacity = (需要存储的元素个数 / 负载因子) + 1。
