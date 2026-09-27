# 模型

| 文件 | 版本 | 参数量 | 网络配置 | 权重摘要（SHA-256 前 16 位） |
| --- | --- | --- | --- | --- |
| `oooi-scmls-v1-preview.pt` | `oooi-scmls-v1-preview` | 10,808,901 | 224 宽 / 7 头 / 编码 7 层 / 解码 8 层，解码器九档相对位置偏置 | `03820782d0761da4` |
| `oooi-scmls-v1.1-preview.pt` | `oooi-scmls-v1.1-preview` | 10,887,548 | 同宽同深，换成三轴有符号整数格距独立嵌入的精确相对位置编码 | `f4a3723c399d5bb8` |

两个文件都是**推理权重**：只含 `model`、`config`、`step`、`seed`、`parameters`、`protocol`，
不含优化器状态，因此体积都在 43 MB 左右。完整训练检查点由
`scripts/training/train.py` 写在实验目录的 `run/final.pt`，需要发布时用
`scripts/training/deploy.py` 转成这种精简格式。

`models.json` 是网页生成服务读取的注册表：

* `path` 相对本目录解析，写出目录外会被拒绝；
* `checkpoint_sha256` 是权重文件的完整摘要，生成服务加载前会重新计算并比对，
  不一致直接报「模型文件摘要与已注册版本不一致」，不会静默用错文件；
* `conditioning` 告诉网页哪些需求字段真的进入网络——两个版本都不读目标 z、
  每轮刻数、连续轮数与每目标负载数，这些字段只决定验收标准；
* `status` 是写进界面模型卡的成绩说明。

两个版本的需求特征都是十二维（几何九项、目标三项），支持范围与判定口径完全一致，
因此可以直接在网页的模型选择器里切换对照。

## 重新发布新权重

```bash
python -m scripts.training.deploy \
  --checkpoint data/generation/<实验目录>/run/final.pt \
  --model-id <版本编号> --name <显示名> \
  --status "<成绩说明>" [--default]
```

命令会写出 `models/<版本编号>.pt` 并更新 `models.json`。
