package com.mcscai.generator

import android.content.Context
import org.json.JSONObject

/**
 * 需求草稿的本机存储。
 *
 * 服务器端草稿存在 SQLite 里并带编辑版本号，用于多设备并发保护；安卓端只有本机一个
 * 写入方，但仍保留版本号字段：网页侧的保存逻辑会比对版本，去掉它会让那段代码需要
 * 分叉，保留它则完全不改网页。
 */
object DraftStore {

    private const val FILE = "draft.json"

    /** 默认需求；与网页 `DEFAULT_TASK` 一致，无时限（`max_ticks` 为 0）。 */
    private const val DEFAULT = """
        {"model_id":"${ModelCatalog.MODEL_ID}","task":{"width":7,"height":5,"depth":2,"targets":[],
        "max_ticks":0,"rounds":3,"load_blocks":10},"group_count":1,"revision":1,"candidate_count":8}
    """

    /** 读取草稿；文件不存在或损坏时返回默认草稿。 */
    fun read(context: Context): String {
        val file = java.io.File(context.filesDir, FILE)
        if (!file.exists()) return DEFAULT.trimIndent().replace("\n", "").replace(" ", "")
        return try {
            val text = file.readText()
            // 校验能解析，损坏时回落到默认值而不是让页面报错。
            JSONObject(text)
            text
        } catch (error: Throwable) {
            DEFAULT.trimIndent().replace("\n", "").replace(" ", "")
        }
    }

    /** 保存草稿并把版本号加一，返回值与写入的草稿同形。 */
    fun write(context: Context, payload: String): String {
        val incoming = JSONObject(payload)
        val stored = JSONObject(read(context))
        incoming.put("revision", stored.optInt("revision", 0) + 1)
        val text = incoming.toString()
        java.io.File(context.filesDir, FILE).writeText(text)
        return text
    }

    /** 首次进入时保证草稿文件存在。 */
    fun ensure(context: Context) {
        val file = java.io.File(context.filesDir, FILE)
        if (!file.exists()) file.writeText(read(context))
    }
}
