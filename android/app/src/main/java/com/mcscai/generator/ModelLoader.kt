package com.mcscai.generator

import android.content.Context
import org.pytorch.LiteModuleLoader
import org.pytorch.LitePyTorchAndroid
import org.pytorch.Module
import org.json.JSONObject
import java.io.File
import java.io.FileOutputStream
import java.security.MessageDigest

/** 模型权重加载状态。 */
enum class ModelState { LOADING, READY, ERROR }

/**
 * 模型权重的加载与持有。
 *
 * 权重随安装包一起分发，首次进入时先解包到应用
 * 私有目录再交给 PyTorch Lite。之所以要先落盘：`LiteModuleLoader.load` 只接受文件路径，而 assets
 * 里的内容不是真实文件。
 *
 * 加载是耗时操作，必须放在后台线程；界面通过 [state] 与 [message] 显示进度。
 */
object ModelLoader {

    private val assets = mapOf(
        ModelCatalog.MODEL_ID to Pair("oooi-scmls-v1-preview.pt", "oooi-scmls-v1-preview.json"),
        ModelCatalog.NEXT_MODEL_ID to Pair("oooi-scmls-v1.1-preview.pt", "oooi-scmls-v1.1-preview.json"),
    )

    @Volatile
    var state: ModelState = ModelState.LOADING
        private set

    /** 当前状态的说明文案，直接显示给用户。 */
    @Volatile
    var message: String = "正在加载模型权重文件"
        private set

    /** 已加载的模块；未就绪时为 null。 */
    private val modules = mutableMapOf<String, Module>()

    /** 取已加载的模块，未就绪时抛异常。 */
    fun require(id: String): Module = modules[id]
        ?: throw IllegalStateException("所选模型权重尚未加载完成")

    /** 是否已就绪。 */
    val ready: Boolean get() = modules.size == assets.size
    fun isReady(id: String): Boolean = modules.containsKey(id)

    /** 算子线程数与服务器上限一致；任务仍串行调度。 */
    val threads: Int = Runtime.getRuntime().availableProcessors().coerceIn(1, 4)

    private fun digest(file: File): String {
        val hash = MessageDigest.getInstance("SHA-256")
        file.inputStream().use { input ->
            val buffer = ByteArray(1 shl 16)
            var count = input.read(buffer)
            while (count != -1) {
                hash.update(buffer, 0, count)
                count = input.read(buffer)
            }
        }
        return hash.digest().joinToString("") { "%02x".format(it) }
    }

    /**
     * 加载权重；可重复调用，已就绪时直接返回。
     *
     * 进度通过 [message] 暴露，界面轮询即可；这里不引入回调，保持与网页桥接的简单对应。
     */
    @Synchronized
    fun load(context: Context, preferredId: String? = null) {
        if (ready) return
        state = ModelState.LOADING
        try {
            val order = buildList {
                preferredId?.takeIf { assets.containsKey(it) }?.let(::add)
                assets.keys.filterNot { it == preferredId }.forEach(::add)
            }
            for (id in order) {
                val pair = assets.getValue(id)
                if (modules.containsKey(id)) continue
                val (asset, metadataAsset) = pair
                message = "正在加载模型权重文件"
                val target = File(context.filesDir, asset)
                val metadata = context.assets.open(metadataAsset).bufferedReader().use { it.readText() }
                val expected = JSONObject(metadata).getString("torch_sha256")
                if (!target.exists() || digest(target) != expected) {
                    message = "正在解包模型权重文件"
                    val temporary = File(context.filesDir, "$asset.tmp")
                    context.assets.open(asset).use { input ->
                        FileOutputStream(temporary).use { output -> input.copyTo(output, 1 shl 16) }
                    }
                    check(digest(temporary) == expected) { "模型文件校验失败：$id" }
                    check(temporary.renameTo(target)) { "无法更新模型文件：$id" }
                }
                message = "正在初始化推理会话"
                modules[id] = LiteModuleLoader.load(target.absolutePath)
            }
            LitePyTorchAndroid.setNumThreads(threads)
            state = ModelState.READY
            message = "模型已就绪"
        } catch (error: Throwable) {
            state = ModelState.ERROR
            message = "模型加载失败：" + (error.message ?: error.javaClass.simpleName)
            modules.clear()
        }
    }
}
