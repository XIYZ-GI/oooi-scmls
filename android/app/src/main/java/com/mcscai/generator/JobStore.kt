package com.mcscai.generator

import android.content.ContentValues
import android.content.Context
import android.database.sqlite.SQLiteDatabase
import android.database.sqlite.SQLiteOpenHelper
import org.json.JSONArray
import org.json.JSONObject
import java.util.UUID

/**
 * 生成历史的本机数据库。
 *
 * 服务器端历史记录存在 SQLite 里；安卓端改用本机数据库，字段与语义保持对应，因此
 * 网页侧的读取与展示逻辑不需要分叉。结果与回放体积较大，单独存成文件而不是塞进数据库
 * 的行里，避免每次列表查询都搬运几十兆的 JSON。
 */
class JobStore private constructor(context: Context) :
    SQLiteOpenHelper(context, "generation.db", null, 1) {

    override fun onCreate(db: SQLiteDatabase) {
        db.execSQL(
            """
            CREATE TABLE jobs (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                model_id TEXT NOT NULL,
                status TEXT NOT NULL,
                progress INTEGER NOT NULL,
                message TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                candidate_count INTEGER NOT NULL,
                task_json TEXT NOT NULL,
                result_json TEXT,
                deleted INTEGER NOT NULL DEFAULT 0
            )
            """.trimIndent()
        )
        // 历史列表按时间倒序翻页，建索引避免记录变多后排序变慢。
        db.execSQL("CREATE INDEX idx_jobs_created ON jobs(created_at DESC)")
    }

    override fun onUpgrade(db: SQLiteDatabase, oldVersion: Int, newVersion: Int) {
        // 目前只有第一版；将来加字段时在此按版本递增迁移，不丢历史记录。
    }

    companion object {
        @Volatile
        private var instance: JobStore? = null

        private fun store(context: Context): JobStore =
            instance ?: synchronized(this) {
                instance ?: JobStore(context.applicationContext).also { instance = it }
            }

        /** 历史列表；按创建时间倒序，删除的软删除记录不返回。 */
        fun list(context: Context): String {
            val cursor = store(context).readableDatabase.query(
                "jobs", arrayOf("id", "name", "model_id", "status", "progress", "message",
                    "created_at", "updated_at", "candidate_count", "task_json"),
                "deleted = 0", null, null, null, "created_at DESC", "200",
            )
            val rows = JSONArray()
            cursor.use {
                while (it.moveToNext()) rows.put(readRow(it))
            }
            return rows.toString()
        }

        /** 读取单个任务，附带结果与回放引用。 */
        fun read(context: Context, jobId: String): String {
            val cursor = store(context).readableDatabase.query(
                "jobs", null, "id = ?", arrayOf(jobId), null, null, null,
            )
            cursor.use {
                if (!it.moveToNext()) throw NoSuchElementException("未找到该生成记录")
                val row = readRow(it)
                val result = it.getString(it.getColumnIndexOrThrow("result_json"))
                if (result != null) {
                    row.put("result", JSONObject(result))
                } else {
                    row.put("result", JSONObject.NULL)
                }
                return row.toString()
            }
        }

        /** 建立一条排队中的任务并返回它。 */
        fun create(context: Context, taskJson: String, candidateCount: Int, modelId: String): JSONObject {
            val id = UUID.randomUUID().toString()
            val now = timestamp()
            val values = ContentValues().apply {
                put("id", id)
                put("name", "生成 " + now.substring(5, 16).replace('T', ' '))
                put("model_id", modelId)
                put("status", "queued")
                put("progress", 0)
                put("message", "排队中")
                put("created_at", now)
                put("updated_at", now)
                put("candidate_count", candidateCount)
                put("task_json", taskJson)
            }
            store(context).writableDatabase.insertOrThrow("jobs", null, values)
            return JSONObject(read(context, id))
        }

        /** 更新任务状态；`resultJson` 为空表示尚未产生结果。 */
        fun update(
            context: Context,
            jobId: String,
            status: String? = null,
            progress: Int? = null,
            message: String? = null,
            resultJson: String? = null,
        ) {
            val values = ContentValues().apply {
                put("updated_at", timestamp())
                if (status != null) put("status", status)
                if (progress != null) put("progress", progress)
                if (message != null) put("message", message)
                if (resultJson != null) put("result_json", resultJson)
            }
            store(context).writableDatabase.update("jobs", values, "id = ?", arrayOf(jobId))
        }

        /** 重命名；空名或与现有记录重名时拒绝。 */
        fun rename(context: Context, jobId: String, name: String): String {
            val trimmed = name.trim()
            if (trimmed.isEmpty()) throw IllegalArgumentException("名称不能为空")
            val cursor = store(context).readableDatabase.query(
                "jobs", arrayOf("id"), "name = ? AND deleted = 0 AND id != ?",
                arrayOf(trimmed, jobId), null, null, null,
            )
            val taken = cursor.use { it.moveToNext() }
            if (taken) throw IllegalArgumentException("已存在同名记录")
            val values = ContentValues().apply {
                put("name", trimmed)
                put("updated_at", timestamp())
            }
            store(context).writableDatabase.update("jobs", values, "id = ?", arrayOf(jobId))
            return read(context, jobId)
        }

        /** 软删除，保留结果文件以便后续恢复。 */
        fun delete(context: Context, jobId: String) {
            val values = ContentValues().apply { put("deleted", 1) }
            store(context).writableDatabase.update("jobs", values, "id = ?", arrayOf(jobId))
        }

        /** 读取某个候选的回放。 */
        fun readReplay(context: Context, jobId: String, candidate: Int): String {
            val file = ReplayStore.path(context, jobId, candidate)
            if (!file.exists()) throw NoSuchElementException("该候选尚未保存回放")
            return file.readText()
        }

        /** 读出任务结果 JSON，供导出与回放使用。 */
        fun result(context: Context, jobId: String): JSONObject {
            val payload = JSONObject(read(context, jobId))
            val result = payload.opt("result")
            if (result == null || result == JSONObject.NULL) {
                throw IllegalStateException("该记录还没有生成结果")
            }
            return result as JSONObject
        }

        private fun readRow(cursor: android.database.Cursor): JSONObject = JSONObject()
            .put("id", cursor.getString(cursor.getColumnIndexOrThrow("id")))
            .put("name", cursor.getString(cursor.getColumnIndexOrThrow("name")))
            .put("model_id", cursor.getString(cursor.getColumnIndexOrThrow("model_id")))
            .put("status", cursor.getString(cursor.getColumnIndexOrThrow("status")))
            .put("progress", cursor.getInt(cursor.getColumnIndexOrThrow("progress")))
            .put("message", cursor.getString(cursor.getColumnIndexOrThrow("message")))
            .put("created_at", cursor.getString(cursor.getColumnIndexOrThrow("created_at")))
            .put("updated_at", cursor.getString(cursor.getColumnIndexOrThrow("updated_at")))
            .put("candidate_count", cursor.getInt(cursor.getColumnIndexOrThrow("candidate_count")))
            .put("task", JSONObject(cursor.getString(cursor.getColumnIndexOrThrow("task_json"))))

        /** 本地时间戳，格式与服务器一致，便于界面直接显示。 */
        private fun timestamp(): String =
            java.text.SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss", java.util.Locale.CHINA)
                .format(java.util.Date())
    }
}
