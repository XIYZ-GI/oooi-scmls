#!/usr/bin/env bash
# 构建本地运行需要的两件产物：Rust 模拟引擎的 Python 扩展 wheel，以及前端静态页面。
#
# 依赖：Rust 工具链、Python 3.11、Node.js 20+、maturin。
#   cargo install maturin --version 1.9.1
#
# 产物：
#   server/wheels/mcscai_engine-*.whl   后端与生成服务镜像安装的引擎扩展
#   frontend/dist/                      Nginx 直接托管的静态页面
set -euo pipefail

readonly ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if ! command -v maturin >/dev/null 2>&1; then
  echo "缺少 maturin，请先执行 cargo install maturin --version 1.9.1" >&2
  exit 1
fi

mkdir -p "${ROOT_DIR}/server/wheels"
maturin build \
  --release \
  --features python \
  --manifest-path "${ROOT_DIR}/engine/Cargo.toml" \
  --out "${ROOT_DIR}/server/wheels"

npm --prefix "${ROOT_DIR}/frontend" ci
npm --prefix "${ROOT_DIR}/frontend" run build

echo "引擎 wheel 与前端静态产物已生成。"
