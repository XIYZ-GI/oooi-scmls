// 应用模块：WebView 套壳 + 原生运算层（Rust）+ PyTorch Lite 推理。
//
// 原生运算层由 cargo-ndk 交叉编译成 libmcscai_native.so 后放进 jniLibs，jniLibs 目录
// 由下面的 buildNative 任务在每次构建前刷新，保证 .so 与 Rust 源码同步。
plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

android {
    namespace = "com.mcscai.generator"
    compileSdk = 34

    defaultConfig {
        applicationId = "com.mcscai.generator"
        minSdk = 26
        targetSdk = 34
        versionCode = 4
        versionName = "0.1.4"
        // 只支持 64 位 ARM：PyTorch Lite 与引擎都按 aarch64 构建，多 ABI 只会让包体翻倍。
        ndk { abiFilters += "arm64-v8a" }
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            // 权重已在模型内部；不额外开混淆，避免误删 JNI 入口。
            proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"), "proguard-rules.pro")
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions { jvmTarget = "17" }
    // assets 里的权重是已压缩的归档，再压一次只会拖慢构建与启动解包。
    androidResources { noCompress += "pt" }

    packaging {
        resources.excludes += setOf("META-INF/*.kotlin_module")
    }
}

// ===== 原生运算层的交叉编译 =====
//
// Rust 侧（android/native）不在 Gradle 的模块图里，这里用 Exec 任务直接调 cargo-ndk，
// 并把产物同步进 jniLibs。
//
// 两点关键：
// 1. `-p mcscai-native` 只构建本 crate。父级引擎声明了 cdylib，不过滤包名时 cargo-ndk
//    会把 libmcscai_engine.so 一起复制进来，包内出现两份引擎副本——多占体积，且两份
//    静态状态各走各的，属于隐患而非冗余。
// 2. 把 native 目录声明为任务输入，改一行 Rust 就会自动重编，不必手动记得跑 cargo。
val nativeDir = file("../native")
val nativeLibsDir = file("src/main/jniLibs")
// 交叉编译需要的工具链一律从环境变量取，不把某台机器的绝对路径写死进构建脚本：
//   ANDROID_HOME / ANDROID_SDK_ROOT：Android SDK 根目录
//   ANDROID_NDK_HOME：NDK 根目录，缺省按 ANDROID_HOME/ndk/<版本> 推导
//   CARGO_HOME 与 RUSTUP_HOME：Rust 工具链位置，缺省用全局默认
val androidSdk = System.getenv("ANDROID_HOME") ?: System.getenv("ANDROID_SDK_ROOT")
val ndkHome = System.getenv("ANDROID_NDK_HOME")
    ?: "$androidSdk/ndk/26.1.10909125"
val cargoHome = System.getenv("CARGO_HOME") ?: "${System.getProperty("user.home")}/.cargo"
val cargoBin = "$cargoHome/bin"

val buildNative by tasks.registering(Exec::class) {
    description = "为 arm64-v8a 交叉编译原生运算层并复制到 jniLibs"
    group = "build"
    workingDir = nativeDir
    // 环境变量显式传入，不依赖 shell 的初始化文件。
    environment("ANDROID_NDK_HOME", ndkHome)
    System.getenv("RUSTUP_HOME")?.let { environment("RUSTUP_HOME", it) }
    environment("CARGO_HOME", cargoHome)
    environment("PATH", "$cargoBin:${System.getenv("PATH")}")
    // `-p` 是 cargo build 的参数，不是 cargo 的全局参数，必须跟在 `ndk` 子命令之后，
    // 否则会被 cargo 本身当成未知参数直接退出。
    commandLine(
        "$cargoBin/cargo", "ndk",
        "-t", "arm64-v8a",
        "-o", nativeLibsDir.absolutePath,
        "build", "-p", "mcscai-native", "--release", "--features", "jni",
    )
    inputs.dir(nativeDir).withPropertyName("rustSources")
    outputs.dir(nativeLibsDir).withPropertyName("nativeLibs")
    doLast {
        // 清掉过滤生效前残留在 jniLibs 里的引擎 cdylib。
        nativeLibsDir.walkTopDown()
            .filter { it.isFile && it.name.endsWith(".so") && it.name != "libmcscai_native.so" }
            .forEach { it.delete() }
    }
}

// 原生库要在打包前就位。
tasks.named("preBuild") { dependsOn(buildNative) }

dependencies {
    implementation("androidx.appcompat:appcompat:1.7.0")
    implementation("androidx.core:core-ktx:1.13.1")
    // WebViewAssetLoader：把 assets 挂到 https 源下。用 file:// 加载页面时模块脚本会被
    // CORS 拦掉，整个前端一行都跑不起来，必须走这个方案。
    implementation("androidx.webkit:webkit:1.11.0")
    // PyTorch Lite：Android 上加载 TorchScript 模型的最小运行时。
    implementation("org.pytorch:pytorch_android_lite:2.1.0")
}
