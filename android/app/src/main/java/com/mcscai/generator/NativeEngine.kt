package com.mcscai.generator

/**
 * 原生运算层的 Kotlin 门面。
 *
 * 全部判定逻辑在 Rust 侧（`android/native`），这里只声明 JNI 入口并做一层薄薄的
 * 类型包装。跨语言接口刻意保持极简：输入输出都是 JSON 字符串，判定本身完全在
 * 原生侧完成，因此每次判定的跨语言往返只有一次。
 */
object NativeEngine {

    init {
        System.loadLibrary("mcscai_native")
    }

    /** 原生运算层版本号。 */
    external fun version(): String

    /**
     * 判定一个候选。
     *
     * @param request `EvaluateRequest` 的 JSON：需求、候选与判定选项。
     * @return 判定结果的 JSON；失败时返回同形的错误对象而不抛异常。
     */
    external fun judge(request: String): String

    /**
     * 校验需求。
     *
     * @return 合法时返回 null，否则返回中文原因。
     */
    external fun validateTask(request: String): String?
}
