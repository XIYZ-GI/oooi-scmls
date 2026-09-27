package com.mcscai.generator

import android.os.Bundle
import android.view.ViewGroup
import android.webkit.WebView
import androidx.appcompat.app.AppCompatActivity
import org.json.JSONObject

/**
 * 套壳宿主：全屏 WebView 加载打包进 assets 的生成器页面。
 *
 * 页面本身不执行任何运算，模型推理、模拟与判定都在 [JobRunner] 里完成。权重加载与
 * 任务执行都不在这里启动——页面会在自己的生命周期里调用桥查询状态，宿主只负责提供
 * 一个能跑 JavaScript 的干净环境。
 *
 * 页面的加载方式见 [WebShell]：必须走 WebViewAssetLoader 伪 https 源，用 `file://`
 * 会让前端一行都跑不起来。
 */
class MainActivity : AppCompatActivity() {

    private lateinit var webView: WebView
    private lateinit var runner: JobRunner

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        runner = JobRunner(applicationContext)
        // 先读取上次退出前保存的模型选择，优先初始化该模型；另一模型随后加载。
        // 这样重新进入应用时不会先启动固定的旧模型。
        val preferredModel = try {
            JSONObject(DraftStore.read(applicationContext)).optString("model_id").takeIf { it.isNotBlank() }
        } catch (_: Throwable) { null }
        Thread { ModelLoader.load(applicationContext, preferredModel) }.start()

        webView = WebView(this)
        WebShell.configure(webView)
        // 桥必须在 loadUrl 之前挂上，否则页面脚本可能在注入前就调用它。
        webView.addJavascriptInterface(WebBridge(applicationContext, runner), "MCSCAI")
        setContentView(webView)
        webView.loadUrl(WebShell.ENTRY)
    }

    override fun onDestroy() {
        runner.shutdown()
        // 先摘出视图树再销毁，避免残留的渲染线程引用已销毁的 WebView。
        (webView.parent as? ViewGroup)?.removeView(webView)
        webView.destroy()
        super.onDestroy()
    }

    /** 返回键优先在页面内后退，便于从结果回到历史列表。 */
    @Deprecated("Deprecated in Java")
    override fun onBackPressed() {
        if (webView.canGoBack()) webView.goBack() else super.onBackPressed()
    }
}
