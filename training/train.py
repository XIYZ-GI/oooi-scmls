"""有限预算监督训练、验证选模和可恢复检查点。"""

import argparse
import json
import math
from pathlib import Path
import random
import time

import torch
from torch.nn import functional as F

from .data import collate, read_examples
from .model import Generator
from .serialization import digest, write_json


def losses(model, batch):
    logits, pushes = model(batch)
    weights = torch.ones(logits.shape[-1], device=logits.device)
    weights[0] = 0.35
    blocks = F.cross_entropy(logits.flatten(0, 1), batch["labels"].flatten(), weight=weights)
    push = F.cross_entropy(pushes, batch["pushes"])
    return blocks + 0.3*push, blocks, push


def main():
    parser = argparse.ArgumentParser(description="阶段一条件结构生成训练")
    parser.add_argument("--data", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--steps", type=int, default=4000)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--seed", type=int, default=20260920)
    parser.add_argument("--max-seconds", type=int, default=10800)
    parser.add_argument("--resume")
    args = parser.parse_args()
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    torch.set_num_threads(4)
    torch.manual_seed(args.seed)
    random.seed(args.seed)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    if device == "cuda":
        torch.backends.cuda.matmul.allow_tf32 = True
    records = read_examples(args.data)
    train = [r for r in records if r["split"] == "train"]
    validation = [r for r in records if r["split"] == "validation"]
    if not train or not validation:
        raise ValueError("训练或验证集合为空")
    model = Generator().to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=3e-4, weight_decay=0.01)
    start_step, best = 0, float("inf")
    if args.resume:
        checkpoint = torch.load(args.resume, map_location=device, weights_only=True)
        if checkpoint["data_sha256"] != digest(Path(args.data).read_text()):
            raise ValueError("恢复训练的数据版本不一致")
        model.load_state_dict(checkpoint["model"])
        optimizer.load_state_dict(checkpoint["optimizer"])
        start_step, best = checkpoint["step"], checkpoint["best_validation_loss"]
        torch.set_rng_state(checkpoint["torch_rng"].cpu())
        if device == "cuda" and checkpoint.get("cuda_rng") is not None:
            torch.cuda.set_rng_state_all([r.cpu() for r in checkpoint["cuda_rng"]])
        random.setstate(checkpoint["python_rng"])
    parameters = model.parameter_report()
    run = {"arguments": vars(args), "config": model.config, "parameters": parameters,
           "torch_version": str(torch.__version__), "device": device,
           "gpu": torch.cuda.get_device_name() if device == "cuda" else None,
           "data_sha256": digest(Path(args.data).read_text()), "precision": "float32_tf32" if device == "cuda" else "float32",
           "loss": {"air_weight": 0.35, "push_weight": 0.3}, "train_examples": len(train), "validation_examples": len(validation)}
    run["code_fingerprints"] = {p.name: digest(p.read_text()) for p in Path(__file__).parent.glob("*.py")}
    write_json(output / "run.json", run)
    print(json.dumps(run, ensure_ascii=False), flush=True)
    started = time.monotonic()
    train_seconds, samples, tokens = 0.0, 0, 0
    last_step = start_step
    metrics = (output / "metrics.jsonl").open("a")

    def save(name, step):
        payload = {"model": model.state_dict(), "optimizer": optimizer.state_dict(), "config": model.config,
                   "step": step, "seed": args.seed, "data_sha256": run["data_sha256"], "best_validation_loss": best,
                   "torch_rng": torch.get_rng_state(), "python_rng": random.getstate(),
                   "cuda_rng": torch.cuda.get_rng_state_all() if device == "cuda" else None}
        temporary = output / (name+".tmp")
        torch.save(payload, temporary)
        temporary.replace(output / name)

    for step in range(start_step+1, args.steps+1):
        model.train()
        batch = collate(random.choices(train, k=args.batch_size), device)
        lr = 3e-4 * min(step/100, 1) * (0.1+0.9*0.5*(1+math.cos(math.pi*step/args.steps)))
        for group in optimizer.param_groups:
            group["lr"] = lr
        tick = time.monotonic()
        loss, blocks, push = losses(model, batch)
        if not torch.isfinite(loss):
            raise RuntimeError("训练损失不是有限值，停止并保留此前检查点")
        optimizer.zero_grad(set_to_none=True)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        optimizer.step()
        if device == "cuda":
            torch.cuda.synchronize()
        train_seconds += time.monotonic()-tick
        samples += args.batch_size
        tokens += int((~batch["padding"]).sum())
        last_step = step
        if step == 1 or step % 50 == 0:
            row = {"step": step, "loss": float(loss.detach()), "blocks": float(blocks.detach()), "push": float(push.detach()),
                   "lr": lr, "seconds": time.monotonic()-started, "samples_per_second": samples/train_seconds,
                   "tokens_per_second": tokens/train_seconds,
                   "gpu_peak_bytes": torch.cuda.max_memory_allocated() if device == "cuda" else 0}
            metrics.write(json.dumps(row)+"\n")
            metrics.flush()
            print(json.dumps(row), flush=True)
        if step % 250 == 0 or step == args.steps:
            model.eval()
            values = []
            with torch.inference_mode():
                for offset in range(0, len(validation), args.batch_size):
                    subset = validation[offset:offset+args.batch_size]
                    values.append((float(losses(model, collate(subset, device))[0]), len(subset)))
            mean = sum(v*n for v, n in values)/sum(n for _, n in values)
            row = {"step": step, "validation_loss": mean}
            print(json.dumps(row), flush=True)
            metrics.write(json.dumps(row)+"\n")
            metrics.flush()
            if mean < best:
                best = mean
                save("best.pt", step)
            save("last.pt", step)
        if time.monotonic()-started >= args.max_seconds:
            save("last.pt", step)
            break
    metrics.close()
    write_json(output / "training-summary.json", {**run, "completed_steps": last_step, "best_validation_loss": best,
               "seconds": time.monotonic()-started, "training_seconds": train_seconds, "samples_per_second": samples/max(train_seconds, 1e-9),
               "gpu_peak_bytes": torch.cuda.max_memory_allocated() if device == "cuda" else 0,
               "functional_success_measured": False})


if __name__ == "__main__":
    main()
