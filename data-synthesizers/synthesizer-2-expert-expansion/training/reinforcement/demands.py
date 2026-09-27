"""只生成需求与条件变换；不生成线路结构或标准答案。"""

from copy import deepcopy
import random

from ..serialization import digest
from ..task import validate_task


def geometry(task):
    """平移、镜像、转置及厚度变体属于同一目标几何，避免跨集合泄漏。"""
    variants = []
    for swap in (False, True):
        for sx in (-1, 1):
            for sy in (-1, 1):
                points = [(sx*t['y' if swap else 'x'], sy*t['x' if swap else 'y'],
                           t['z'], t['order']) for t in task['targets']]
                left, bottom = min(p[0] for p in points), min(p[1] for p in points)
                variants.append(sorted((x-left, y-bottom, z, order) for x, y, z, order in points))
    return digest(min(variants))


def random_task(rng, index=None):
    # 分层抽取数量与时序，避免随机填充让大网格、高密度需求淹没其他需求。
    band = rng.choices((0, 1, 2), (.55, .35, .10))[0] if index is None else index % 3
    count = rng.randint(*((1, 5), (6, 12), (13, 20))[band])
    depth = rng.choices((2, 3, 4), (.4, .4, .2))[0]
    sizes = [(w, h) for w in range(1, 16) for h in range(1, 16)
             if count <= w*h <= min(100, 512//depth)]
    # 多数在紧凑范围，保留大边距与长条需求，尺寸不会固定为7×5。
    weights = [1/(1+max(0, w*h-count*2)/8) for w, h in sizes]
    width, height = rng.choices(sizes, weights)[0]
    cells = [(x, y) for x in range(width) for y in range(height)]
    if rng.random() < .5:
        cx, cy = rng.choice(cells)
        # 随机优先级仅控制聚集程度，不规定红石机构或目标固定形状。
        cells.sort(key=lambda p: abs(p[0]-cx)+abs(p[1]-cy)+rng.random()*4)
        chosen = cells[:count]
    else:
        chosen = rng.sample(cells, count)
    groups = rng.choices((1, 2, 3, 4), (.40, .35, .20, .05))[0]
    groups = min(groups, count)
    orders = list(range(1, groups+1))+[rng.randint(1, groups) for _ in range(count-groups)]
    rng.shuffle(orders)
    task = dict(width=width, height=height, depth=depth, max_ticks=48, rounds=3, load_blocks=10,
                targets=[dict(x=x, y=y, z=0, order=order) for (x, y), order in zip(chosen, orders)])
    task['targets'].sort(key=lambda t: (t['x'], t['y']))
    return task


def variation(task, rng, compact=False):
    task = deepcopy(task)
    if rng.random() < .5:
        task['width'], task['height'] = task['height'], task['width']
        for t in task['targets']:
            t['x'], t['y'] = t['y'], t['x']
    for axis, size in [('x', 'width'), ('y', 'height')]:
        if rng.random() < .5:
            for t in task['targets']:
                t[axis] = task[size]-1-t[axis]
    if compact:
        # 只有需求变严格，结构仍由策略重新生成，不删改已有成功结构。
        task['depth'] = max(2, task['depth']-1)
    elif rng.random() < .35:
        for axis, size in [('x', 'width'), ('y', 'height')]:
            extra = rng.randint(0, min(3, 15-task[size]))
            shift = rng.randint(0, extra)
            if (task[size]+extra)*task['height' if size == 'width' else 'width']*task['depth'] <= 512:
                task[size] += extra
                for t in task['targets']:
                    t[axis] += shift
    task['targets'].sort(key=lambda t: (t['x'], t['y']))
    return validate_task(task)


def advance_goal(task, rng):
    """在模型已经解决的需求上增加一个目标；不接触任何结构答案。"""
    task = deepcopy(task)
    occupied = {(t['x'], t['y']) for t in task['targets']}
    cells = [(x, y) for x in range(task['width']) for y in range(task['height']) if (x, y) not in occupied]
    if not cells or len(occupied) >= 32:
        return task
    weights = [1/(1+min(abs(x-tx)+abs(y-ty) for tx, ty in occupied)) for x, y in cells]
    x, y = rng.choices(cells, weights)[0]
    groups = max(t['order'] for t in task['targets'])
    order = groups+1 if groups < 4 and rng.random() < .2 else rng.randint(1, groups)
    task['targets'].append(dict(x=x, y=y, z=0, order=order))
    task['targets'].sort(key=lambda t: (t['x'], t['y']))
    return validate_task(task)


class DemandSampler:
    def __init__(self, experts, excluded, seed, frontier_fraction=0.0):
        self.experts = experts
        self.excluded = set(excluded)
        self.rng = random.Random(seed)
        self.successes = {}
        self.frontier_fraction = frontier_fraction

    def add_success(self, task):
        self.successes[geometry(task)] = deepcopy(task)
        if len(self.successes) > 10000:
            del self.successes[next(iter(self.successes))]

    def sample(self, count):
        rows = []
        while len(rows) < count:
            draw = self.rng.random()
            if draw < .2:
                task = variation(self.rng.choice(self.experts)['task'], self.rng)
                source = 'expert'
            elif draw >= .8 and self.successes:
                advancing = self.rng.random() < self.frontier_fraction
                task = variation(self.rng.choice(list(self.successes.values())), self.rng,
                                 compact=not advancing and self.rng.random() < .35)
                task = advance_goal(task, self.rng) if advancing else task
                source = 'frontier' if advancing else 'success'
            else:
                task, source = random_task(self.rng), 'random'
            if geometry(task) in self.excluded:
                continue
            rows.append({'task': task, 'source': source, 'task_id': digest(task)[:24]})
        return sorted(rows, key=lambda r: r['task']['width']*r['task']['height']*r['task']['depth'])
