//! JNI 导出层：把原生运算能力暴露给 Kotlin。
//!
//! 跨语言接口刻意保持极简：输入输出都是 JSON 字符串。判定本身完全在 Rust 内部
//! 完成，每次判定的跨语言往返只有一次，因此这里的序列化开销可以忽略。

use jni::{
    objects::{JClass, JString},
    sys::jstring,
    JNIEnv,
};

/// 把 Rust 字符串转成 Java 字符串；失败时返回 null。
fn to_java(env: &mut JNIEnv<'_>, value: &str) -> jstring {
    match env.new_string(value) {
        Ok(text) => text.into_raw(),
        Err(_) => std::ptr::null_mut(),
    }
}

/// 读取 Java 字符串；失败时返回空串。
fn from_java(env: &mut JNIEnv<'_>, value: &JString<'_>) -> String {
    env.get_string(value)
        .map(|text| text.to_string_lossy().into_owned())
        .unwrap_or_default()
}

/// 判定一个候选。`request` 是 `EvaluateRequest` 的 JSON，返回判定结果的 JSON。
#[no_mangle]
pub extern "system" fn Java_com_mcscai_generator_NativeEngine_judge(
    mut env: JNIEnv<'_>,
    _class: JClass<'_>,
    request: JString<'_>,
) -> jstring {
    let payload = from_java(&mut env, &request);
    let response = match crate::judge(&payload) {
        Ok(value) => value,
        Err(message) => error_json(&message),
    };
    to_java(&mut env, &response)
}

/// 原生运算层的版本号。
#[no_mangle]
pub extern "system" fn Java_com_mcscai_generator_NativeEngine_version(
    mut env: JNIEnv<'_>,
    _class: JClass<'_>,
) -> jstring {
    let version = crate::VERSION.to_string();
    to_java(&mut env, &version)
}

/// 校验需求。成功返回 `null`，失败返回中文原因。
#[no_mangle]
pub extern "system" fn Java_com_mcscai_generator_NativeEngine_validateTask(
    mut env: JNIEnv<'_>,
    _class: JClass<'_>,
    request: JString<'_>,
) -> jstring {
    let payload = from_java(&mut env, &request);
    match serde_json::from_str::<crate::task::Task>(&payload) {
        Ok(task) => match crate::task::validate(&task) {
            Ok(()) => std::ptr::null_mut(),
            Err(message) => to_java(&mut env, &message),
        },
        Err(error) => to_java(&mut env, &format!("需求解析失败：{error}")),
    }
}

/// 把失败信息包装成与成功路径同形的 JSON。
fn error_json(message: &str) -> String {
    serde_json::json!({
        "accepted": false,
        "reason": message,
        "rounds": [],
        "protocol": crate::protocol::PROTOCOL,
        "load_blocks": crate::protocol::LOAD_BLOCKS,
        "simulator_started": false,
        "simulated_ticks": 0,
        "design_rule": crate::protocol::RULE,
    })
    .to_string()
}
