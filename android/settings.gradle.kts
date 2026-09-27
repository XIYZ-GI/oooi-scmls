// 安卓工程入口：只包含一个应用模块。
// 原生运算层（android/native）是独立的 Rust crate，由 app 模块里的 buildNative 任务
// 通过 cargo-ndk 交叉编译，不在 Gradle 的模块图里，因此这里只声明 app。
pluginManagement {
    repositories {
        google()
        mavenCentral()
        gradlePluginPortal()
    }
}

dependencyResolutionManagement {
    repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
    repositories {
        google()
        mavenCentral()
    }
}

rootProject.name = "mcscai-generator"
include(":app")
