"""迁移现有生成器，以分族均衡采样学习紧凑机制。"""

from collections import defaultdict
import hashlib
import json
import math
from pathlib import Path
import random
import time

import torch

from ..data import collate, read_examples
from ..inference import load_model
from ..serialization import digest, write_json
from ..train import losses


def main():
    root = Path("data/generation/stage3")
    plan = json.loads((root/"experiment-plan.json").read_text())
    output = Path("runs/stage3")
    output.mkdir(parents=True, exist_ok=True)
    seed = plan["seed"]
    torch.manual_seed(seed)
    torch.set_num_threads(4)
    torch.backends.cuda.matmul.allow_tf32 = True
    rng = random.Random(seed)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model, initial = load_model(plan["initial_checkpoint"], device)
    records = read_examples(root/"examples.jsonl")
    families = defaultdict(lambda: defaultdict(list))
    validation = defaultdict(list)
    for row in records:
        family = "legacy" if row["family"].startswith("legacy_") else row["family"]
        if row["split"] == "train":
            families[family][row["group"]].append(row)
        elif row["split"] == "validation":
            validation[family].append(row)
    for name in plan["family_sampling"]:
        if not families[name]:
            raise ValueError("训练课程为空："+name)
    optimizer = torch.optim.AdamW(model.parameters(), lr=plan["learning_rate"], weight_decay=0.01)
    run = {"plan": plan, "parameters": model.parameter_report(), "config": model.config,
           "transfer_fraction": 1.0, "initial_step": initial["step"],
           "initial_checkpoint_sha256": hashlib.sha256(Path(plan["initial_checkpoint"]).read_bytes()).hexdigest(),
           "data_digest": digest((root/"examples.jsonl").read_text()),
           "code_sha256": {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in Path("training").rglob("*.py")},
           "torch": str(torch.__version__), "gpu": torch.cuda.get_device_name() if device == "cuda" else None,
           "precision": "float32_tf32", "process_loss": False}
    write_json(output/"run.json", run)
    best, best_step = float("inf"), 0
    started = time.monotonic()

    def save(name, step, score):
        payload = {"model": model.state_dict(), "config": model.config, "step": step, "seed": seed,
                   "data_sha256": run["data_digest"], "validation_loss": score}
        tmp = output/(name+".tmp")
        torch.save(payload, tmp)
        tmp.replace(output/name)

    with (output/"metrics.jsonl").open("w") as log:
        for step in range(1, plan["steps"]+1):
            model.train()
            # 先抽任务族再抽来源；同批同族，避免小课程被大成品填充拖慢。
            family = rng.choices(list(plan["family_sampling"]), weights=list(plan["family_sampling"].values()))[0]
            groups = list(families[family])
            subset = [rng.choice(families[family][rng.choice(groups)]) for _ in range(plan["batch_size"])]
            batch = collate(subset, device)
            lr = plan["learning_rate"]*min(step/100, 1)*(0.1+0.9*0.5*(1+math.cos(math.pi*step/plan["steps"])))
            for group in optimizer.param_groups:
                group["lr"] = lr
            loss, _, _ = losses(model, batch)
            if not torch.isfinite(loss):
                raise RuntimeError("训练损失非有限，停止本轮")
            optimizer.zero_grad(set_to_none=True)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            if step == 1 or step % 100 == 0:
                row = {"step": step, "family": family, "loss": float(loss.detach()),
                       "seconds": time.monotonic()-started,
                       "gpu_peak_bytes": torch.cuda.max_memory_allocated() if device == "cuda" else 0}
                log.write(json.dumps(row)+"\n"); log.flush()
                print(json.dumps(row, ensure_ascii=False), flush=True)
            if step % 500 == 0 or step == plan["steps"]:
                model.eval()
                values = {}
                with torch.inference_mode():
                    for family, examples in validation.items():
                        sums, count = 0, 0
                        for offset in range(0, len(examples), 8):
                            part = examples[offset:offset+8]
                            sums += float(losses(model, collate(part, device))[0])*len(part)
                            count += len(part)
                        values[family] = sums/count
                score = sum(values.values())/len(values)
                row = {"step": step, "validation": values, "selection_loss": score}
                log.write(json.dumps(row)+"\n"); log.flush()
                print(json.dumps(row), flush=True)
                if score < best:
                    best, best_step = score, step
                    save("best.pt", step, score)
                save("last.pt", step, score)
                torch.save({"optimizer": optimizer.state_dict(), "step": step, "torch_rng": torch.get_rng_state(),
                            "python_rng": rng.getstate(), "cuda_rng": torch.cuda.get_rng_state_all() if device == "cuda" else None}, output/"optimizer-last.pt")
            if time.monotonic()-started > plan["max_training_seconds"]:
                save("last.pt", step, None)
                break
    write_json(output/"training-summary.json", {**run, "completed_steps": step, "best_step": best_step,
        "best_validation_loss": best, "seconds": time.monotonic()-started,
        "gpu_peak_bytes": torch.cuda.max_memory_allocated() if device == "cuda" else 0})


if __name__ == "__main__":
    main()
