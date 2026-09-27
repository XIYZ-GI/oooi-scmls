"""解压服务器训练包后运行；需要 AutoDL 的 PyTorch 镜像。"""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import torch


def main():
    parser = argparse.ArgumentParser(description="训练移动线局部修改评分器")
    parser.add_argument("--data", type=Path, default=Path("."), help="解压后的数据目录")
    parser.add_argument("--output", type=Path, default=Path("model.json"), help="输出模型")
    parser.add_argument("--epochs", type=int, default=400, help="最多训练轮次")
    args = parser.parse_args()
    torch.manual_seed(20260920)
    manifest = json.loads((args.data / "manifest.json").read_text())
    records = [json.loads(line) for line in (args.data / "candidates.jsonl").read_text().splitlines() if line]
    records = [r for r in records if "error" not in r["result"]]
    train = [r for r in records if r["split"] == "train"]
    valid = [r for r in records if r["split"] == "validation"]
    positives = sum(bool(r["result"].get("load_pass")) for r in train)
    if positives < 3 or len(train) - positives < 3:
        raise SystemExit("训练来源中的正例和负例各至少需要三条，请先继续服务器搜索")
    device = "cuda" if torch.cuda.is_available() else "cpu"

    def tensors(rows):
        return (torch.tensor([r["features"] for r in rows], dtype=torch.float32, device=device),
                torch.tensor([float(r["result"].get("load_pass", False)) for r in rows], device=device))

    x, y = tensors(train)
    model = torch.nn.Linear(len(manifest["featureNames"]), 1).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=0.02, weight_decay=0.02)
    balance = torch.where(y == 1, len(y) / (2 * positives), len(y) / (2 * (len(y) - positives)))
    best_loss, best = float("inf"), None
    for epoch in range(max(1, args.epochs)):
        optimizer.zero_grad()
        loss = (torch.nn.functional.binary_cross_entropy_with_logits(model(x).flatten(), y, reduction="none") * balance).mean()
        loss.backward()
        optimizer.step()
        with torch.no_grad():
            vx, vy = tensors(valid) if valid else (x, y)
            score = torch.nn.functional.binary_cross_entropy_with_logits(model(vx).flatten(), vy).item()
            if score < best_loss:
                best_loss = score
                best = {k: v.detach().clone() for k, v in model.state_dict().items()}
        if (epoch + 1) % 100 == 0:
            print(f"轮次 {epoch + 1}，训练损失 {loss.item():.4f}，选模损失 {score:.4f}")
    model.load_state_dict(best)
    result = {"provenance": manifest["provenance"], "featureVersion": 1, "features": manifest["featureNames"],
              "weights": [model.bias.item(), *model.weight.detach().cpu().flatten().tolist()],
              "trainRows": len(train), "positive": positives, "negative": len(train) - positives,
              "trainedAt": datetime.now(timezone.utc).isoformat()}
    if valid:
        vx, vy = tensors(valid)
        accuracy = ((model(vx).flatten() >= 0) == (vy >= 0.5)).float().mean().item()
        count = int(vy.sum().item())
        result["validation"] = {"rows": len(valid), "positive": count, "accuracy": accuracy,
                                "majorityBaseline": max(count, len(valid) - count) / len(valid)}
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2))
    print(f"模型已保存到 {args.output}，运行设备：{device}。测试来源未用于训练或选模。")


if __name__ == "__main__":
    main()
