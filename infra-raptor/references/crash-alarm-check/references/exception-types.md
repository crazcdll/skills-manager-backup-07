# 常见异常类型与根因模式

## Android

| 异常类型 | 常见根因 |
|---|---|
| `IllegalArgumentException: No view found for id` | Fragment 被 commit 到没有对应容器 View 的 Activity |
| `ClassNotFoundException` | 混淆配置问题、动态加载类缺失 |
| `NullPointerException` | 生命周期问题，对象提前释放 |
| `IllegalStateException: Fragment already added` | Fragment 重复 add |
| `NoSuchMethodError` | 版本兼容性问题，方法签名变更 |
| `ANR` | 主线程阻塞、耗时操作未异步处理 |
| `OutOfMemoryError` | 内存泄漏、图片/大对象加载过多 |
| `SecurityException` | 权限缺失、敏感操作未授权 |
| `SIGSEGV / SIGBUS` | Native 层指针操作错误、JNI 调用异常 |

## iOS

| 异常类型 | 常见根因 |
|---|---|
| `EXC_BAD_ACCESS` | 野指针访问、对象已释放后访问 |
| `NSInvalidArgumentException` | 方法调用参数错误 |
| `SIGABRT` | 断言失败或未捕获异常 |
| `Unrecognized Selector` | 对象未实现方法，OC 动态消息转发失败 |
| `NSRangeException` | 数组越界访问 |
| `NSInternalInconsistencyException` | 状态不一致，常见于 UI 或多线程场景 |
| `Mach Exception` | 底层系统异常，权限/资源访问 |

## 鸿蒙

| 异常类型 | 常见根因 |
|---|---|
| `Fatal signal 6 (SIGABRT)` | 系统主动终止，业务或系统层断言失败 |
| `Fatal signal 11 (SIGSEGV)` | 内存访问违规，Native 层指针错误 |
| `AppNotRespondingException` | 主线程阻塞 |
| `ClassNotFoundException` | 动态加载类缺失、模块化兼容性问题 |
| `ModuleLoadFailedException` | 鸿蒙动态模块加载失败，版本兼容或依赖缺失 |
