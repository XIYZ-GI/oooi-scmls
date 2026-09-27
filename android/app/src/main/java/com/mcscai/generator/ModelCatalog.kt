package com.mcscai.generator

import org.json.JSONArray
import org.json.JSONObject

/**
 * 模型清单。
 *
 * 安卓端内置两个可切换的离线模型，网页侧按「清单 + 默认项」读取。
 */
object ModelCatalog {

    /** 唯一的模型编号；保留服务器侧的注册编号，便于与历史任务对应。 */
    const val MODEL_ID = "combined-noz-relpos-12d-10.8m"

    /** 对用户显示的名字。 */
    const val MODEL_NAME = "oooi-scmls-v1-preview"

    const val NEXT_MODEL_ID = "oooi-scmls-v1.1-preview"
    const val NEXT_MODEL_NAME = "oooi-scmls-v1.1-preview"

    /** 参数量，取自导出时的统计。 */
    const val PARAMETERS = 10_808_901

    /**
     * 该版本模型真正读取的需求字段。
     *
     * 十二维需求模型不把每轮刻数、连续轮数、每目标负载数读进网络，这三项只决定验收
     * 标准。网页据此隐藏两个输入框，并在提交时把它们固定成协议值。
     */
    val CONDITIONING = mapOf(
        "size" to true,
        "targets" to true,
        "max_ticks" to false,
        "rounds" to false,
        "load_blocks" to true,
        "target_z" to false,
    )

    /** 组装成网页期望的清单 JSON。 */
    fun describe(): String {
        val conditioning = JSONObject()
        for ((key, value) in CONDITIONING) conditioning.put(key, value)
        fun item(id: String, name: String, parameters: Int) = JSONObject()
            .put("id", id)
            .put("name", name)
            .put("status", "本机离线推理")
            .put("ready", ModelLoader.isReady(id))
            .put("parameters", parameters)
            .put("device", "本机")
            .put("conditioning", conditioning)
        val models = JSONArray()
            .put(item(MODEL_ID, MODEL_NAME, PARAMETERS))
            .put(item(NEXT_MODEL_ID, NEXT_MODEL_NAME, 10_887_548))
        return JSONObject()
            .put("models", models)
            .put("default", MODEL_ID)
            .toString()
    }

    fun name(id: String): String = if (id == NEXT_MODEL_ID) NEXT_MODEL_NAME else MODEL_NAME
}
