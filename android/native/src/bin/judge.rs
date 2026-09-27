//! 一致性验证用的批量判定入口。
//!
//! 从标准输入按行读取判定请求 JSON，逐条判定后按行输出结果 JSON。
//! 宿主机上的 `android/tools/consistency.py` 用它和 Python 参考实现逐字段比对，
//! 是判定器移植的验收闸门。

use std::io::{self, BufRead, Write};

fn main() {
    let stdin = io::stdin();
    let stdout = io::stdout();
    let mut out = io::BufWriter::new(stdout.lock());

    for line in stdin.lock().lines() {
        let line = match line {
            Ok(value) => value,
            Err(_) => break,
        };
        let trimmed = line.trim();
        if trimmed.is_empty() {
            continue;
        }
        // 无论成功失败都要输出一行，保持与输入行数一一对应，便于上层逐行比对。
        let response = match mcscai_native::judge(trimmed) {
            Ok(value) => value,
            Err(message) => serde_json::json!({"accepted": false, "reason": message}).to_string(),
        };
        if writeln!(out, "{response}").is_err() {
            break;
        }
    }
    let _ = out.flush();
}
