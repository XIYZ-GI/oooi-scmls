"""生成独立的同规则一倍和五倍课程，骨架及目标几何同时隔离。"""

from collections import Counter
from concurrent.futures import ProcessPoolExecutor
import hashlib
import json
import math
import random
import time

from ..serialization import digest, write_json
from ..reinforcement.demands import geometry
from .config import ROOT, BASELINE_RECORDS, EXPANDED_RECORDS, SEED, WORKERS
from .composition import compose
from .presentation import variants
from .admission import admit
from .gate import require_all


def partition(key):
    n=int(digest(['expansion_split',key])[:8],16)%10
    return 'development' if n==0 else 'heldout' if n==1 else 'train'


def compact(row):
    value=row['evaluation']
    row['evaluation']=dict(accepted=value['accepted'],protocol=value['protocol'],
        reason=value['reason'],rounds=value['rounds'],design_rule=value['design_rule'],
        foundation={k:value.get('foundation',{}).get(k) for k in ('accepted','translation','activation','activation_required','piston_count')})
    return row


def main():
    require_all()
    if (ROOT/'dataset-complete.json').exists():
        return
    lib=json.loads((ROOT/'module-library.json').read_text())
    rng=random.Random(SEED);counts=Counter();shapes=Counter();groups=set();geometries=set();seen=set();base_geometries=Counter()
    reserved=json.loads((ROOT/'reserved-cases.json').read_text())['cases']
    excluded={geometry(r['task']) for r in reserved}
    excluded.update(geometry(r['task']) for r in json.loads((ROOT/'experts.json').read_text()))
    files={'train':ROOT/'train-5x.jsonl','development':ROOT/'development.jsonl','heldout':ROOT/'heldout.jsonl'}
    # 已准入记录保留；重启后重建索引。随机流状态在每批准入后保存。
    for split,path in files.items():
        if not path.exists():
            continue
        with path.open() as handle:
            for line in handle:
                r=json.loads(line);seen.add(r['id']);counts[split]+=1
                if split=='train':
                    g=geometry(r['task']);geometries.add(g);groups.add(r['group'])
                    shapes[f"{len(r['task']['targets'])}目标/{len({t['order'] for t in r['task']['targets']})}时序"]+=1
                    if r.get('presentation')==0:base_geometries[g]+=1
    state=ROOT/'dataset-state.json'
    if state.exists():
        saved=json.loads(state.read_text())
        def nested_tuple(v):
            return tuple(nested_tuple(x) for x in v) if isinstance(v,list) else v
        rng.setstate(nested_tuple(saved['rng']))
    wanted=dict(train=EXPANDED_RECORDS,development=128,heldout=128)
    attempts=0;started=time.monotonic();reasons=Counter();base_seen=set()
    with ProcessPoolExecutor(max_workers=WORKERS) as pool:
        while any(counts[k]<v for k,v in wanted.items()):
            batch=[]
            while len(batch)<WORKERS*8:
                attempts+=1
                size=rng.choice((2,3,3,4,4,5,5,6))
                row=compose(lib,rng,size,min_nodes=size-1)
                if row is None or row['id'] in base_seen:
                    continue
                base_seen.add(row['id'])
                split=partition(row['group'])
                if counts[split]>=wanted[split]:
                    continue
                row['split']=split
                # 单级和单目标始终只占少量，避免简单构造把样本预算吃完。
                if split=='train' and len(row['topology'])==1 and rng.random()<.8:
                    continue
                row['task']['max_ticks']=48 if size<=5 else 64
                batch.append(row)
            accepted=[]
            for row in pool.map(admit,batch,chunksize=2):
                reasons[row['evaluation']['reason'] or '完整通过']+=1
                if not row['evaluation']['accepted']:
                    continue
                g=geometry(row['task']);split=row['split']
                if g in excluded or partition(g)!=split or (split=='train' and base_geometries[g]>=4):
                    continue
                base_geometries[g]+=1
                row['base_id']=row['id']
                accepted.extend(variants(compact(row),rng))
            # 新增的留白、旋转和厚度展示也经过同一模拟门槛。
            presented=[]
            for r in accepted:
                if r['id'] not in seen and r['presentation']:
                    presented.append(r)
            checked={r['id']:r for r in pool.map(admit,presented,chunksize=2)}
            with files['train'].open('a') as train, files['development'].open('a') as dev, files['heldout'].open('a') as held:
                streams={'train':train,'development':dev,'heldout':held}
                for raw in accepted:
                    row=checked.get(raw['id'],raw)
                    if not row['evaluation']['accepted'] or row['id'] in seen:
                        continue
                    split=row['split']
                    if counts[split]>=wanted[split]:
                        continue
                    row=compact(row);row['usage']='fit' if split=='train' else split
                    streams[split].write(json.dumps(row,ensure_ascii=False,separators=(',',':'))+'\n')
                    seen.add(row['id']);counts[split]+=1
                    if split=='train':
                        groups.add(row['group']);geometries.add(geometry(row['task']))
                        shapes[f"{len(row['task']['targets'])}目标/{len({t['order'] for t in row['task']['targets']})}时序"]+=1
                for stream in streams.values():stream.flush()
            write_json(state,dict(rng=rng.getstate(),counts=dict(counts),attempts=attempts,
                geometries=len(geometries),groups=len(groups),shapes=dict(shapes),reasons=dict(reasons),seconds=time.monotonic()-started))
            if counts['train']>=BASELINE_RECORDS and not (ROOT/'dataset-1x-ready.json').exists():
                with files['train'].open() as src,(ROOT/'train-1x.jsonl').open('w') as dst:
                    for i,line in enumerate(src):
                        if i>=BASELINE_RECORDS:break
                        dst.write(line)
                write_json(ROOT/'dataset-1x-ready.json',dict(records=BASELINE_RECORDS,nested_in='train-5x.jsonl',
                    sha256=hashlib.sha256((ROOT/'train-1x.jsonl').read_bytes()).hexdigest()))
            print(json.dumps(dict(counts=dict(counts),geometries=len(geometries),groups=len(groups),attempts=attempts),ensure_ascii=False),flush=True)
    write_json(ROOT/'dataset-complete.json',dict(counts=dict(counts),baseline_records=BASELINE_RECORDS,
        multiplier=5,geometries=len(geometries),groups=len(groups),shapes=dict(shapes),
        seconds=time.monotonic()-started,seed=SEED,workers=WORKERS,
        files={k:dict(path=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for k,p in files.items()},
        note='一倍集为同构造随机流的前24894条，嵌套于五倍集；另报独立几何和单元骨架数，空间增强不冒充独立机械设计。全部18个专家已用于机制研究。'))


if __name__=='__main__':
    main()
