# 数据合成器

`oooi-scmls-v1.1-preview` 的训练集共 **170,226 条**「需求 + 结构 + 推动点」记录，
由下面四份代码合成。四份都是完整的 Python 工程根目录，各自带一份 `training/`
包，运行时把它当作当前目录即可（不要与仓库根的 `training/` 混用）。

| 目录 | 入训记录 | 主要构造方式 | 源码来源 |
| --- | --- | --- | --- |
| `synthesizer-1-legacy-curriculum` | 23,612 | 紧凑课程构造（`compact`、`compact_round2`）与扩量增广（`expanded`） | 从当前仓库整理，**缺少完整历史快照**，不能保证逐字节还原 |
| `synthesizer-2-expert-expansion` | 57,856 | 专家结构扩量（`expert_expansion`）与早期强化学习（`reinforcement`） | 主要生成文件与历史摘要一致；两项公共依赖后来有变化 |
| `synthesizer-3-structure-generator` | 77,374 | 引导生长 + 分层接力构造（`structure_generator`） | 从当时保存的源码快照提取 |
| `synthesizer-4-regular-generator-v2` | 11,384 | 规律密集构造（`regular_generator_v2`）与带反馈生长的结构生成器 | 从当时冻结的运行源码提取 |

合计 23,612 + 57,856 + 77,374 = 158,842 条早期数据，加上第 4 份的 11,384 条新生成器数据，
正好是 v1.1-preview 使用的 170,226 条。`oooi-scmls-v1-preview` 用的是前 158,842 条的子集。

## 运行前提

四份代码都依赖两个东西：

1. **`mcscai_engine`**：本仓库的 Rust 模拟引擎。这些目录不随代码附带编译好的
   `.so`，需要自己构建：

   ```bash
   cd /path/to/oooi-scmls
   python3 -m venv .venv && . .venv/bin/activate
   pip install maturin==1.9.1
   maturin develop --release --features python --manifest-path engine/Cargo.toml
   ```

   构建完成后 `import mcscai_engine` 就能用，四份代码都能直接找到它。

2. **Python 3.11 + PyTorch CPU**：合成过程要用模型与判定器筛选候选。

   ```bash
   pip install -r training/requirements.txt
   ```

## 运行方式

每份代码都以自己的目录为工程根：

```bash
cd data-synthesizers/synthesizer-3-structure-generator
python -m training.structure_generator.batch \
  --output ../../data/generation/my-run --workers 8 --count 20000
```

可用的命令行入口（都支持 `--help`）：

| 目录 | 入口 |
| --- | --- |
| 1 | `training.expanded.{train,evaluate,run_evaluation,finish,publish,average,coverage}`、`training.compact_round2.{train,finish,publish,failures}`、`training.compact.deliver` |
| 2 | `training.expert_expansion.curriculum.{run,stage4_dataset,mixed_dataset,eval_set,fresh_eval_set,legacy_train,legacy_eval,migrate,showcase}`、`training.expert_expansion.pushdrive.run`、`training.reinforcement.{run,train,report}` |
| 3 | `training.structure_generator.batch`、`training.structure_generator.run`、`training.structure_generator.{benchmark,thin_suite,thin_showcase,showcase}` |
| 4 | `training.structure_generator.batch`、`training.structure_generator.run`、`training.regular_generator_v2`（模块内提供计划与准入） |

## 合成结果怎么进训练

批量构造把每条记录写进 `records.sqlite3` 的 `records` 表（`body` 列是完整 JSON）。
把四份产出交给数据集冻结脚本：

```bash
python -m scripts.training.dataset \
  --name oooi-scmls-v1.1-preview \
  --output data/generation/oooi-scmls-v1.1-preview \
  --source <合成器1产出>/records.sqlite3 \
  --source <合成器2产出>/dataset.jsonl.gz \
  --source <合成器3产出>/records.sqlite3 \
  --source <合成器4产出>/records.sqlite3
```

脚本会写出 `dataset.jsonl` 与 `manifest.json`，训练入口据此校验数据身份。

## 训练数据为什么不在仓库里

训练数据总量在数百 MB 到 GB 量级，且体积与内容都随构造批次变化，放进源码仓库既臃肿
也无法保证可复现。这里交付的是**能重新合成数据、并能把结果接进训练的全部代码**；
两个发布模型的权重要么直接用 `models/` 里发布好的文件，要么按上面的流程重新合成数据
再训练。
