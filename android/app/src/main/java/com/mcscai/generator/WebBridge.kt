package com.mcscai.generator

import android.content.Context
import android.webkit.JavascriptInterface
import org.json.JSONObject

/**
 * 暴露给网页的桥。
 *
 * 网页侧 `src/bridge/index.ts` 声明的字段名必须与本类的方法名逐字对应。所有方法都在
 * WebView 的 JavaScript 线程上被调用，因此内部一律把重活交给 [JobRunner]，不在此阻塞。
 *
 * 返回值统一是 JSON 字符串：成功是结果本体，失败是 `{"error": "中文原因"}`。
 * 这样网页侧只需要一处错误处理，不必在每次调用外面套 try/catch。
 */
class WebBridge(private val context: Context, private val runner: JobRunner) {

    /** 原生运算层版本号。 */
    @JavascriptInterface
    fun version(): String = NativeEngine.version()

    /** 模型权重加载状态。 */
    @JavascriptInterface
    fun modelState(): String = JSONObject()
        .put("state", ModelLoader.state.name.lowercase())
        .put("message", ModelLoader.message)
        .toString()

    /** 读取安卓端内置的模型清单。 */
    @JavascriptInterface
    fun readModel(): String = ModelCatalog.describe()

    /** 读取需求草稿。 */
    @JavascriptInterface
    fun readDraft(): String = guard { DraftStore.read(context) }

    /** 保存需求草稿。 */
    @JavascriptInterface
    fun writeDraft(payload: String): String = guard { DraftStore.write(context, payload) }

    /** 列出历史任务。 */
    @JavascriptInterface
    fun listJobs(): String = guard { JobStore.list(context) }

    /** 提交生成任务，立刻返回任务编号。 */
    @JavascriptInterface
    fun submitJob(payload: String): String = guard { runner.submit(payload) }

    /** 读取任务状态。 */
    @JavascriptInterface
    fun readJob(jobId: String): String = guard { JobStore.read(context, jobId) }

    /** 取消任务。 */
    @JavascriptInterface
    fun cancelJob(jobId: String) {
        runner.cancel(jobId)
    }

    /** 删除任务。 */
    @JavascriptInterface
    fun deleteJob(jobId: String) {
        guard { JobStore.delete(context, jobId); "null" }
    }

    /** 重命名任务。 */
    @JavascriptInterface
    fun renameJob(jobId: String, name: String): String =
        guard { JobStore.rename(context, jobId, name) }

    /** 读取指定候选的逐帧回放。 */
    @JavascriptInterface
    fun readReplay(jobId: String, candidate: Int): String =
        guard { JobStore.readReplay(context, jobId, candidate) }

    /** 导出候选为基岩版结构文件；写入成功后返回文件名。 */
    @JavascriptInterface
    fun exportCandidate(jobId: String, candidate: Int, assembly: Boolean): String =
        guard { JSONObject.quote(StructureExport.write(context, jobId, candidate, assembly)) }

    /** 统一的错误包装：把异常翻成网页可读的中文提示。 */
    private inline fun guard(action: () -> String): String =
        try {
            action()
        } catch (error: Throwable) {
            JSONObject()
                .put("error", error.message ?: error.javaClass.simpleName)
                .toString()
        }
}
