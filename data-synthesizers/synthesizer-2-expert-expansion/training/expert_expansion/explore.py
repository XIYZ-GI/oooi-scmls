"""保存模块组合的实际准入结果和多样性，供逐步改进构造规则。"""

import argparse
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
import json
import random
import time

from ..serialization import digest, write_json
from ..reinforcement.demands import geometry
from .config import ROOT
from .modules import reconstruct
from .composition import compose
from .admission import admit


def main():
    parser=argparse.ArgumentParser(description='运行单元组合准入')
    parser.add_argument('--count',type=int,default=512)
    parser.add_argument('--seed',type=int,default=2026092201)
    args=parser.parse_args()
    library=json.loads((ROOT/'module-library.json').read_text())
    audit=json.loads((ROOT/'expert-audit.json').read_text())
    originals={r['name']:r for r in audit}
    reconstruction=[]
    for recipe in library['recipes']:
        row=reconstruct(recipe,library);source=originals[recipe['name']]
        key=lambda b:tuple(b['position'][a] for a in ('x','y','z'))
        same=sorted(row['proposal']['blocks'],key=key)==sorted(source['proposal']['blocks'],key=key)
        assert same and row['task']==source['task'] and row['proposal']['push']==source['proposal']['push']
        reconstruction.append(dict(name=row['name'],exact_targets_and_orders=True,
            reconstruction_only=True,modules=len(recipe['nodes']),accepted=source['evaluation']['accepted']))
    write_json(ROOT/'reconstruction.json',reconstruction)
    rng=random.Random(args.seed);rows=[];seen=set();attempts=0
    while len(rows)<args.count and attempts<args.count*100:
        attempts+=1
        size=rng.choice((2,3,4,5,6))
        row=compose(library,rng,size,min_nodes=size-1)
        if row is not None and row['id'] not in seen:
            seen.add(row['id']);rows.append(row)
    print(json.dumps(dict(assembled=len(rows),attempts=attempts)),flush=True)
    stem=f'exploration-{args.seed}'
    counts=Counter();levels=Counter();unique=set();accepted=0;started=time.monotonic()
    with ProcessPoolExecutor(max_workers=6) as pool, (ROOT/(stem+'.jsonl')).open('w') as out:
        for i,row in enumerate(pool.map(admit,rows)):
            out.write(json.dumps(row,ensure_ascii=False,separators=(',',':'))+'\n');out.flush()
            counts[row['evaluation']['reason'] or '完整通过']+=1
            if row['evaluation']['accepted']:
                accepted+=1;unique.add(geometry(row['task']))
                levels[f"{len(row['topology'])}单元/{len({t['order'] for t in row['task']['targets']})}时序"]+=1
            if (i+1)%32==0:
                print(json.dumps(dict(completed=i+1,accepted=accepted,geometries=len(unique)),ensure_ascii=False),flush=True)
    report=dict(assembled=len(rows),attempts=attempts,accepted=accepted,geometries=len(unique),
                levels=dict(levels),reasons=dict(counts),seconds=time.monotonic()-started)
    write_json(ROOT/(stem+'-report.json'),report)
    print(json.dumps(report,ensure_ascii=False),flush=True)


if __name__=='__main__':
    main()
