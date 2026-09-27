package com.mcscai.generator

import android.annotation.SuppressLint
import android.util.Log
import android.webkit.ConsoleMessage
import android.webkit.WebChromeClient
import android.webkit.WebResourceRequest
import android.webkit.WebResourceResponse
import android.webkit.WebView
import android.webkit.WebViewClient
import androidx.webkit.WebViewAssetLoader

/**
 * 套壳 WebView 的加载配置。
 *
 * **页面不能用 `file://` 加载。** Vite 打包出的产物是 `<script type="module">`，而模块
 * 脚本一律按 CORS 规则抓取；`file://` 的源是不透明的，安卓 WebView 会直接拒绝执行模块脚本。
 * 表现是最难查的那种：HTML 正常显示、CSS 也生效（底色是淡蓝），但 JS 一行都没跑，
 * `#root` 始终为空——整片界面全白，且没有任何可见报错，logcat 里也不显眼。
 *
 * 因此改用 [WebViewAssetLoader] 把 assets 挂到 `https://appassets.androidplatform.net/`
 * 这个伪域名下。页面从此有一个正常的 https 源：模块脚本可加载，localStorage 与
 * IndexedDB 也才真正可用（不透明源下这两者本身也受限）。
 */
object WebShell {

    /** 伪域名；这是 WebViewAssetLoader 的固定域名，不要改。 */
    private const val HOST = "appassets.androidplatform.net"

    /**
     * 页面入口。
     *
     * 路径 `/assets/www/index.html` 中的 `www` 是 assets 下的真实目录名；网页里的相对
     * 路径（`./assets/xxx.js`、`./textures/...`）会相对本 URL 解析，正好落在同一目录下。
     */
    const val ENTRY = "https://$HOST/assets/www/index.html"

    private const val TAG = "MCSCAI-Web"

    @SuppressLint("SetJavaScriptEnabled")
    fun configure(webView: WebView) {
        val loader = WebViewAssetLoader.Builder()
            .addPathHandler("/assets/", WebViewAssetLoader.AssetsPathHandler(webView.context))
            .build()

        webView.settings.apply {
            javaScriptEnabled = true
            domStorageEnabled = true
            // 页面已走 https 源，不再需要读 file://，关掉更安全。
            allowFileAccess = false
            allowContentAccess = false
            mediaPlaybackRequiresUserGesture = true
            textZoom = 100
        }
        webView.webViewClient = object : WebViewClient() {
            override fun shouldInterceptRequest(
                view: WebView,
                request: WebResourceRequest,
            ): WebResourceResponse? = loader.shouldInterceptRequest(request.url)
        }
        // 把网页的 console 转发到 logcat。真机上出问题时，这是唯一能看到前端报错的通道；
        // 本应用没有任何网络请求，不存在把日志传出去的问题。
        webView.webChromeClient = object : WebChromeClient() {
            override fun onConsoleMessage(message: ConsoleMessage): Boolean {
                Log.i(TAG, "${message.messageLevel()} ${message.message()} @${message.lineNumber()}")
                return true
            }
        }
    }
}
