"""只给需求的生成入口，权重以安全的张量检查点加载。"""

import argparse
import json
from pathlib import Path

import torch

from .constants import BOS
from .data import batch_tasks
from .model import Generator
from .serialization import decode_structure, positions, write_json
from .task import validate_task


def load_model(path, device):
    checkpoint = torch.load(path, map_location=device, weights_only=True)
    model = Generator(**checkpoint["config"]).to(device)
    model.load_state_dict(checkpoint["model"])
    model.eval()
    return model, checkpoint


@torch.inference_mode()
def generate(model, tasks, device, temperature=0.0):
    batch = batch_tasks(tasks, device, **model.feature_options)
    memory = model.encode(batch)
    length = batch["padding"].shape[1]
    inputs = torch.full((len(tasks), 1), BOS, device=device, dtype=torch.long)
    generated = []
    for index in range(length):
        logits, _ = model.decode(inputs, batch, memory)
        values = logits[:, -1].float()
        token = values.argmax(-1) if temperature == 0 else torch.multinomial((values/temperature).softmax(-1), 1).squeeze(-1)
        token = token.masked_fill(batch["padding"][:, index], 0)
        generated.append(token)
        if index+1 < length:
            inputs = torch.cat([inputs, token[:, None]], dim=1)
    tokens = torch.stack(generated, dim=1)
    _, hidden = model.decode(inputs, batch, memory)
    push = model.push_logits(hidden, tokens, batch).argmax(-1)
    return [decode_structure(task, tokens[i, :len(positions(task))].tolist(), int(push[i])) for i, task in enumerate(tasks)]


def main():
    parser = argparse.ArgumentParser(description="从需求生成完整初始移动线，不读取专家答案")
    parser.add_argument("--checkpoint", required=True)
    parser.add_argument("--task", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--seed", type=int, default=41)
    parser.add_argument("--candidates", type=int, default=8)
    args = parser.parse_args()
    if not 1 <= args.candidates <= 64:
        parser.error("候选预算必须在一至六十四之间")
    torch.manual_seed(args.seed)
    torch.set_num_threads(4)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model, checkpoint = load_model(args.checkpoint, device)
    task = validate_task(json.loads(Path(args.task).read_text()))
    proposals = generate(model, [task], device) + generate(model, [task]*(args.candidates-1), device, 0.7) if args.candidates > 1 else generate(model, [task], device)
    from .evaluator import evaluate
    evaluations = [evaluate(task, proposal) for proposal in proposals]
    success = next((i for i, result in enumerate(evaluations) if result["accepted"]), None)
    write_json(args.output, {"task": task, "proposals": proposals, "evaluations": evaluations,
                             "solution": proposals[success] if success is not None else None,
                             "status": "success" if success is not None else "not_found", "seed": args.seed,
                             "checkpoint_step": checkpoint["step"]})


if __name__ == "__main__":
    main()
