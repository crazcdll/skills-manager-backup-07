---
ruleType: Model Request
description: Java集合处理规范，包含equals和hashCode处理、Collections类返回的immutable对象使用、集合转数组、Comparator实现类要求、集合初始化等集合处理要求
category: Java编码规范
priority: medium
---

# Java集合处理规范

## 一、说明

本规范详细描述了Java编码规范中的集合处理要求。集合是Java编程中最常用的数据结构，正确使用集合能够提高代码质量和性能。

## 二、规则内容

### java-l1:JAVA-03.N001 [强制] equals和hashCode的处理规范

equals和hashCode的处理，遵循如下规则：

**说明**：
- 仅在必要时重写equals
- 重写equals时，必须重写hashCode
- 自定义对象作为基于哈希表实现的Set集合元素或Map键时，必须重写equals和hashCode

### java-l1:JAVA-03.N002 [强制] Collections类返回的immutable对象的使用规范

Collections类返回的immutable对象，不可对其进行添加或者删除元素操作，否则会抛出UnsupportedOperationException异常。

### java-l1:JAVA-03.N003 [强制] 集合转数组的规范

集合转数组时，必须使用集合的toArray(T[] array)，传入类型完全一致的数组，建议数组长度为0。以确保转换过程高效且安全，避免ArrayStoreException异常。

### java-l1:JAVA-03.N004 [强制] Comparator实现类的规范

Comparator实现类要满足三个条件：非对称性、传递性、一致性，避免Arrays.sort，Collections.sort抛IllegalArgumentException异常。

### java-l1:JAVA-03.N005 [推荐] 集合初始化的规范

若对集合容量有预估，则初始化时指定初始容量大小，避免随着元素增加反复调用resize()扩容，影响性能。

**说明**：使用HashMap时可以调用构造方法HashMap(int initialCapacity)进行初始化，initialCapacity = (需要存储的元素个数 / 负载因子) + 1。

## 三、执行要求

1. 所有集合操作必须遵循本规范要求
2. 代码审查时重点检查集合使用的规范性
3. 对于违反规范的代码必须及时整改
4. 新代码必须严格按照本规范编写

## 四、示例

以下示例仅用于说明规则边界与意图，不代表唯一实现方式；实际生成或审查代码时，应优先复用项目现有框架、工具类、SDK 与命名，并以是否满足规则约束为判断标准。

### java-l1:JAVA-03.N003 集合转数组的规范示例

#### good case:

```java
List<String> list = new ArrayList<>(2);
list.add("mei");
list.add("tuan");
// 传入长度为0的数组，toArray方法会自动创建一个新数组，大小足以容纳集合中的所有元素
String[] array = list.toArray(new String[0]);
```

### java-l1:JAVA-03.N004 Comparator实现类的规范示例

#### bad case:

```java
List<Integer> list = Arrays.asList(
    0, 7, 0, 5, 0, 0, 4, 5,
    4, 3, 5, 7, 7, 5, 5, 6,
    9, 6, 0, 2, 8, 9, 1, 3,
    7, 9, 2, 9, 3, 2, 7, 8);
// 错误：违反 非对称性条件
Comparator<Integer> faultyComparator = new Comparator<Integer>() {
    @Override
    public int compare(Integer x, Integer y) {
        // 故意设计的逻辑错误，当x和y相等时，返回非零值
        return x > y ? 1 : -1;
    }
};
// 使用错误的比较器进行排序，抛出IllegalArgumentException（异常非必现，与输入有关）
Collections.sort(list, faultyComparator);
```

## 五、规范执行要点

### 核心要求
1. **equals和hashCode**：重写equals必须同时重写hashCode,作为Set元素或Map键时必须重写两者
2. **不可变集合**：Collections返回的immutable对象禁止添加/删除操作
3. **集合转数组**：必须使用toArray(T[] array)方法,传入类型一致的数组,建议长度为0
4. **Comparator实现**：必须满足非对称性、传递性、一致性三个条件
5. **容量初始化**：有预估容量时必须指定初始容量,计算公式:(元素个数/负载因子)+1

### 强制禁止
- ✗ 禁止重写equals但不重写hashCode
- ✗ 禁止对immutable集合进行add/remove操作(会抛UnsupportedOperationException)
- ✗ 禁止使用toArray()无参方法(返回Object[]类型,类型不安全)
- ✗ 禁止Comparator不满足三个条件(会抛IllegalArgumentException)
- ✗ 禁止高容量集合不指定初始容量(频繁扩容影响性能)

### 代码审查检查点
- [ ] equals和hashCode是否成对重写
- [ ] 自定义对象作为Set元素或Map键时是否重写了equals和hashCode
- [ ] 是否对immutable集合进行了修改操作
- [ ] 集合转数组是否使用了正确的toArray方法
- [ ] Comparator是否满足三个条件(非对称性、传递性、一致性)
- [ ] 容量可预估的集合是否指定了初始容量