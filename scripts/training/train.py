"""三万步监督训练：缓存编码、按体积分批，保存可续训的完整状态。

两个发布模型共用这一份训练循环，只换 ``config`` 与数据集。训练必须在 GPU 上跑，
断点里写入数据指纹与网络配置，换了任何一项都会拒绝续训。
"""

import json
import math
from pathlib import Path
import random
import signal
import time

import torch

from training.accelerated.cache import EncodedCache
from training.data import read_examples
from training.model import Generator
from training.serialization import digest, write_json
from training.train import losses
from .config import STEPS, SEED


def batch_size(length, mask_tensors=1):
    """同时限制有效格数与注意力矩阵规模，长网格不会被过大的批次撑爆显存。

    解码器启用相对位置偏置后，除了编码器的偏置，自注意力与交叉注意力各多一张
    同规模浮点掩码，按掩码张数等比收紧批量。
    """
    return max(1, min(192, 16384 // length, 8000000 // (length * length * mask_tensors)))


def run(root, config, parameters, steps=STEPS, seed=SEED, resume_lr=3e-5,
        learning_rate=3e-4, warmup=200):
    root = Path(root)
    torch.set_num_threads(2)
    torch.set_num_interop_threads(1)
    if not torch.cuda.is_available():
        raise RuntimeError("本次训练必须在 GPU 上执行；CPU 只用于推理与评估")
    torch.backends.cuda.matmul.allow_tf32 = True
    torch.manual_seed(seed)
    rng = random.Random(seed)
    rows = read_examples(root / "dataset.jsonl")
    manifest = json.loads((root / "manifest.json").read_text())
    expected = manifest.get("training_records")
    assert expected and len(rows) <= expected, f"训练记录数异常：{len(rows)}/{expected}"
    if len(rows) != expected:
        print(json.dumps(dict(warning="读取时按规则过滤了训练记录", kept=len(rows), built=expected),
                         ensure_ascii=False), flush=True)
    model = Generator(**config).cuda()
    assert model.parameter_report()["total"] == parameters, "网络参数量与实验配置不一致"
    optimizer = torch.optim.AdamW(model.parameters(), lr=learning_rate, weight_decay=0.01, fused=True)
    output = root / "run"
    output.mkdir(exist_ok=True)
    fingerprint = digest((root / "dataset.jsonl").read_text())
    ordered = sorted(rows, key=lambda r: r["task"]["width"] * r["task"]["height"] * r["task"]["depth"])
    lengths = [r["task"]["width"] * r["task"]["height"] * r["task"]["depth"] for r in ordered]
    cache = EncodedCache(rows, "cuda", **model.feature_options)
    # 相对位置编码同样每步持有编码器与两组注意力掩码；精确编码只有编码器一张。
    mask_tensors = 3 if model.decoder_relative is not None else 1
    start_step, samples, previous_seconds = 0, 0, 0.0
    stopping = [False]
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, lambda *_: stopping.__setitem__(0, True))
    if (output / "last.pt").exists():
        checkpoint = torch.load(output / "last.pt", map_location="cuda", weights_only=True)
        assert checkpoint["data_sha256"] == fingerprint and checkpoint["config"] == config
        # 允许在已完成步数之后继续训练（延长总步数），续训段用小学习率余弦衰减。
        assert checkpoint["steps"] <= steps and checkpoint["seed"] == seed
        previous_total = checkpoint["steps"]
        model.load_state_dict(checkpoint["model"])
        optimizer.load_state_dict(checkpoint["optimizer"])
        rng.setstate(checkpoint["python_rng"])
        torch.set_rng_state(checkpoint["torch_rng"].cpu())
        torch.cuda.set_rng_state_all([state.cpu() for state in checkpoint["cuda_rng"]])
        start_step, samples, previous_seconds = checkpoint["step"], checkpoint["samples"], checkpoint["seconds"]
        extended = steps > previous_total
        print(json.dumps(dict(resumed_from=start_step), ensure_ascii=False), flush=True)
    else:
        extended = False
    run_info = dict(config=config, parameters=model.parameter_report(), seed=seed, steps=steps,
                    initialization="随机初始化；只恢复本实验自己的检查点",
                    data_sha256=fingerprint, train_examples=len(rows),
                    torch=str(torch.__version__), gpu=torch.cuda.get_device_name(), precision="bf16",
                    cache_bytes=cache.bytes, loss=dict(air_weight=.35, push_weight=.3),
                    learning_rate=learning_rate, warmup_steps=warmup, weight_decay=.01,
                    selection="无验证集，正式评估统一使用训练结束时的最终检查点")
    write_json(output / "run.json", run_info)
    print(json.dumps(run_info, ensure_ascii=False), flush=True)
    started = time.monotonic()

    def save(name, step):
        checkpoint = dict(model=model.state_dict(), optimizer=optimizer.state_dict(), config=config,
                          parameters=model.parameter_report(), seed=seed, steps=steps, step=step,
                          data_sha256=fingerprint, python_rng=rng.getstate(), torch_rng=torch.get_rng_state(),
                          cuda_rng=torch.cuda.get_rng_state_all(), samples=samples,
                          seconds=previous_seconds + time.monotonic() - started)
        path = output / name
        torch.save(checkpoint, path.with_suffix(".tmp"))
        path.with_suffix(".tmp").replace(path)

    with (output / "metrics.jsonl").open("a") as metrics:
        for step in range(start_step + 1, steps + 1):
            model.train()
            index = rng.randrange(len(ordered))
            size = batch_size(lengths[index], mask_tensors)
            window = max(16, size * 3)
            low, high = max(0, index - window), min(len(ordered), index + window + 1)
            subset = [ordered[i] for i in rng.sample(range(low, high), min(size, high - low))]
            batch = cache.batch(subset)
            if extended:
                progress = step - start_step
                lr = resume_lr * .5 * (1 + math.cos(math.pi * progress / max(1, steps - start_step)))
            else:
                lr = learning_rate * min(step / warmup, 1) * (.1 + .9 * .5 * (1 + math.cos(math.pi * step / steps)))
            for group in optimizer.param_groups:
                group["lr"] = lr
            optimizer.zero_grad(set_to_none=True)
            with torch.autocast("cuda", dtype=torch.bfloat16):
                loss, blocks, push = losses(model, batch)
            if not torch.isfinite(loss):
                raise RuntimeError("损失非有限值，停止并保留上一检查点")
            loss.backward()
            # 记录裁剪前的梯度范数，用于定位失稳发生的位置。
            norm = torch.nn.utils.clip_grad_norm_(model.parameters(), 1.)
            optimizer.step()
            samples += len(subset)
            if step == 1 or step % 50 == 0:
                record = dict(step=step, loss=float(loss.detach()), blocks=float(blocks.detach()),
                              push=float(push.detach()), lr=lr, grad_norm=float(norm.detach()),
                              batch=len(subset), samples=samples,
                              seconds=previous_seconds + time.monotonic() - started,
                              gpu_peak_bytes=torch.cuda.max_memory_allocated())
                metrics.write(json.dumps(record) + "\n")
                metrics.flush()
                print(json.dumps(record), flush=True)
            if step % 500 == 0 or step == steps or stopping[0]:
                save("last.pt", step)
                record = dict(step=step, checkpoint="已保存", seconds=round(time.monotonic() - started, 1))
                metrics.write(json.dumps(record, ensure_ascii=False) + "\n")
                metrics.flush()
                print(json.dumps(record, ensure_ascii=False), flush=True)
            if stopping[0]:
                raise SystemExit("已保存训练断点，训练尚未完成")
    save("final.pt", steps)
    write_json(output / "training-summary.json",
               dict(run=run_info, completed_steps=steps, samples=samples,
                    seconds=previous_seconds + time.monotonic() - started,
                    gpu_peak_bytes=torch.cuda.max_memory_allocated()))
    print(json.dumps(dict(completed_steps=steps, samples=samples), ensure_ascii=False), flush=True)
