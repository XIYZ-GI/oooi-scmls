"""在随机骨架内交换观察者与输出位置，预先声明新目标并验证完整候选。"""

from .config import FACING, VECTORS
from .geometry import add
from .layered_score import score
from .front_output import allowed as output_allowed


def improve(search, mode='either', rounds=4):
    """不减少目标或修改同推刻数；新旧目标位置均记录，失败恢复整个候选。"""
    layout = search.layout
    changes = []
    for _ in range(rounds):
        initial_score = score(layout, mode)
        baseline = layout.checkpoint()
        trials = []
        outputs = {v['piston']: (i, v['tick']) for i, v in enumerate(layout.outputs)}
        columns = {p[:2] for p in outputs}
        for operation_index, operation in enumerate(layout.operations):
            for old in operation['added']:
                if not output_allowed(layout, old):
                    continue
                block = layout.blocks.get(old, {})
                if block.get('kind') != 'observer' or old[:2] in columns:
                    continue
                charge = add(old, VECTORS[block['facing']])
                for direction in VECTORS.values():
                    new = add(charge, direction)
                    output = outputs.get(new)
                    if output and output[1] == operation['tick']+4:
                        trials.append((operation_index, old, new, FACING[tuple(-v for v in direction)], output[0]))
        search.rng.shuffle(trials)
        ranked = []
        for operation_index, old, new, facing, output_index in trials:
            layout.restore(baseline)
            layout.blocks[old] = dict(kind='piston', facing='positive_z')
            layout.blocks[new] = dict(kind='observer', facing=facing)
            layout.outputs[output_index]['piston'] = old
            if any(q[:2] == old[:2] and q[2] > old[2] for q in layout.blocks):
                continue
            quality = score(layout, mode)
            if quality <= initial_score:
                continue
            operation = layout.operations[operation_index]
            operation['added'] = [new if p == old else p for p in operation['added']]
            if 'preferred_outputs' in operation:
                operation['preferred_outputs'] = [old if p == new else p for p in operation['preferred_outputs']]
            ranked.append((quality, layout.checkpoint(), dict(
                observer_from=old, observer_to=new, output_from=new, output_to=old,
                output_tick=layout.outputs[output_index]['tick'])))
        ranked.sort(key=lambda item: item[0], reverse=True)
        accepted = False
        for _, candidate, change in ranked:
            if search.simulations >= search.options.get('simulation_budget', 48):
                break
            layout.restore(candidate)
            if search.valid():
                changes.append(change)
                accepted = True
                break
        if not accepted:
            layout.restore(baseline)
            break
    return changes
