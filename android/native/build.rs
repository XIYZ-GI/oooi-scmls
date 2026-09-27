//! 从引擎清单读取版本号，避免原生层与引擎的版本字符串各自漂移。
//!
//! 判定结果里的 `engine_version` 必须与 Python 侧 `mcscai_engine.__version__`
//! 一致，否则同一份结构在两端会被当成不同引擎产出的结果。

use std::{fs, path::Path};

fn main() {
    let manifest = Path::new("../..").join("engine").join("Cargo.toml");
    println!("cargo:rerun-if-changed={}", manifest.display());
    let version = fs::read_to_string(&manifest)
        .ok()
        .and_then(|text| {
            // 引擎清单里第一个 `version = "x.y.z"` 即包版本。
            text.lines()
                .map(str::trim)
                .find_map(|line| line.strip_prefix("version"))
                .and_then(|rest| rest.split('"').nth(1))
                .map(str::to_string)
        })
        .unwrap_or_else(|| "0.0.0".to_string());
    println!("cargo:rustc-env=MCSCAI_ENGINE_VERSION={version}");
}
