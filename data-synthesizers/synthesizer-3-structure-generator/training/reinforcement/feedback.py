"""从真实世界快照提取奖励；不改变评估器的完整通过条件。"""


class Feedback:
    def __init__(self, task, members, loads):
        self.task, self.members, self.loads = task, members, loads
        self.cycles = []
        self.cycle = 0
        self.tick = 0
        self.ticks = []
        self.current = {}

    def begin(self, cycle):
        if self.current:
            self.cycles.append(self.current)
        self.cycle, self.tick = cycle, 0
        self.ticks = [None]*len(self.loads)
        self.current = {}

    def observe(self, snapshot, step):
        self.tick += step
        actual = {b['id']: b['position'] for b in snapshot['blocks']}
        complete = []
        for i, (target, group) in enumerate(zip(self.task['targets'], self.loads)):
            done = all(actual.get(block_id) == dict(x=target['x'], y=target['y'], z=z+self.cycle+1)
                       for block_id, z in group)
            complete.append(done)
            if done and self.ticks[i] is None:
                self.ticks[i] = self.tick
        matched, pairs = 0, 0
        for i in range(len(self.loads)):
            for j in range(i):
                pairs += 1
                if complete[i] and complete[j] and self.ticks[i] is not None and self.ticks[j] is not None:
                    expected = self.task['targets'][i]['order']-self.task['targets'][j]['order']
                    observed = self.ticks[i]-self.ticks[j]
                    matched += (expected > 0)-(expected < 0) == (observed > 0)-(observed < 0)
        translation = sum(actual.get(block_id) == {**p, 'z': p['z']+self.cycle+1}
                          for block_id, p in self.members)/len(self.members)
        self.current = {'cycle': self.cycle+1, 'target_fraction': sum(complete)/len(complete),
                        'timing_fraction': matched/pairs if pairs else float(all(complete)),
                        'translation_fraction': translation, 'ticks': list(self.ticks),
                        'completed_targets': sum(complete)}

    def finish(self, result):
        result['feedback'] = {'cycles': [*self.cycles, *([self.current] if self.current else [])]}


def reward(task, proposal, result):
    if result['accepted']:
        zs = [b['position']['z'] for b in proposal['blocks']]
        depth = max(zs)-min(zs)+1
        return 2.0+.2*(1-depth/task['depth'])+.05*(1-len(zs)/(task['width']*task['height']*task['depth']))
    if not result.get('simulator_started'):
        return -0.2
    cycles = result.get('feedback', {}).get('cycles', [])
    current = cycles[-1] if cycles else {}
    # 失败奖励严格小于1；完整成功至少2。未完成的时序对不能获得时序分。
    return (.45*current.get('target_fraction', 0)+.20*current.get('timing_fraction', 0)
            +.15*current.get('translation_fraction', 0)+.20*len(result['rounds'])/task['rounds'])


def simulate(row):
    from ..evaluator import evaluate
    result = evaluate(row['task'], row['proposal'], feedback=True)
    return {'evaluation': result, 'reward': reward(row['task'], row['proposal'], result)}
