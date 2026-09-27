# 原生运算层通过 JNI 按名字查找方法，混淆后名字一变就会 UnsatisfiedLinkError。
-keepclasseswithmembernames class com.mcscai.generator.NativeEngine { native <methods>; }
-keep class com.mcscai.generator.NativeEngine { *; }

# 网页通过 @JavascriptInterface 反射调用这些方法，同样不能改名或裁掉。
-keepclassmembers class com.mcscai.generator.WebBridge {
    @android.webkit.JavascriptInterface <methods>;
}

# PyTorch Lite 内部依赖 JNI 与反射。
-keep class org.pytorch.** { *; }
-dontwarn org.pytorch.**
