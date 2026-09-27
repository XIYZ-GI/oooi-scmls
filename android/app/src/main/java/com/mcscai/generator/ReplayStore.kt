package com.mcscai.generator

import android.content.Context
import java.io.File

/**
 * 回放的落盘位置。
 *
 * 回放逐帧包含完整快照，体积远大于结果本身，因此单独存成文件：历史列表查询只读数据库
 * 的行，不会顺带搬运这些大对象。这与服务器端「列表走数据库、回放走独立文件」的做法一致。
 */
object ReplayStore {

    /** 回放文件路径；目录不存在时创建。 */
    fun path(context: Context, jobId: String, candidate: Int): File {
        val directory = File(context.filesDir, "replays/$jobId")
        if (!directory.exists()) directory.mkdirs()
        return File(directory, "replay-$candidate.json")
    }

    /** 写入回放。 */
    fun write(context: Context, jobId: String, candidate: Int, payload: String) {
        val target = path(context, jobId, candidate)
        // 先写临时文件再改名，避免中途失败留下半截 JSON。
        val temporary = File(target.parentFile, target.name + ".tmp")
        temporary.writeText(payload)
        temporary.renameTo(target)
    }
}
