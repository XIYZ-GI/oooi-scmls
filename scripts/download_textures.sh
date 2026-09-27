#!/usr/bin/env bash
set -euo pipefail

readonly COMMIT="921fafb05c93abeae56c2f2868cd8f942bdbcc0f"
readonly BASE_URL="https://raw.githubusercontent.com/Mojang/bedrock-samples/${COMMIT}/resource_pack/textures/blocks"
readonly TARGET_DIR="${1:-frontend/public/textures/blocks}"

readonly TEXTURES=(
  glass.png
  glazed_terracotta_light_blue.png
  honey_bottom.png
  honey_side.png
  honey_top.png
  iron_block.png
  observer_back.png
  observer_back_lit.png
  observer_front.png
  observer_side.png
  observer_top.png
  piston_bottom.png
  piston_inner.png
  piston_side.png
  piston_top_normal.png
  piston_top_sticky.png
  redstone_block.png
  slime.png
)

mkdir -p "${TARGET_DIR}"
for texture in "${TEXTURES[@]}"; do
  curl --fail --location --silent --show-error \
    "${BASE_URL}/${texture}" \
    --output "${TARGET_DIR}/${texture}"
done

echo "已下载 ${#TEXTURES[@]} 个固定版本方块贴图。"

