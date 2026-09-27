"""固定八视角预算的完整验收；仅开发集用于选择检查点。"""

from collections import Counter
import hashlib
import json
from pathlib import Path
import time

from ..accelerated.symmetry import generate_symmetric
from ..evaluator import evaluate
from ..serialization import write_json


def assess(model, records, pool, path=None):
    model.eval()
    started = time.monotonic()
    pending = []
    ordered = sorted(records, key=lambda r: r['task']['width']*r['task']['height']*r['task']['depth'])
    for start in range(0, len(ordered), 8):
        batch = ordered[start:start+8]
        groups = generate_symmetric(model, batch, 'cuda', 8, 41)
        for record, proposals in zip(batch, groups):
            futures = [pool.submit(evaluate, record['task'], proposal) for proposal in proposals]
            pending.append((record, proposals, futures))
    rows = []
    for record, proposals, futures in pending:
        evaluations = [f.result() for f in futures]
        accepted = any(e['accepted'] for e in evaluations)
        rows.append({**record, 'accepted': accepted, 'proposals': proposals, 'evaluations': evaluations})
    counts = Counter(r['family'] for r in rows)
    passed = Counter(r['family'] for r in rows if r['accepted'])
    report = {'tasks': len(rows), 'successes': sum(r['accepted'] for r in rows),
              'families': {key: {'tasks': count, 'successes': passed[key]} for key, count in counts.items()},
              'seconds': time.monotonic()-started, 'candidate_budget': 8, 'protocol': 'eight_view_greedy_v1'}
    if path:
        path = Path(path)
        path.mkdir(parents=True, exist_ok=True)
        with (path/'results.jsonl').open('w') as handle:
            for row in rows:
                handle.write(json.dumps(row, ensure_ascii=False)+'\n')
        write_json(path/'report.json', report)
    return report


def file_sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()
