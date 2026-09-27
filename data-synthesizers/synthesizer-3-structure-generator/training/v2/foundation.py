"""独立记录整线搬运与活塞激活；由调用方选择激活是否参与准入。"""

from ..constants import AXES


class Foundation:
    def __init__(self, task, members, snapshot, require_activation=True):
        self.task = task
        self.require_activation = require_activation
        self.members = dict(members)
        initial = {b['id']: b for b in snapshot['blocks']}
        self.pistons = {i for i in self.members if initial[i]['kind'] in ('piston', 'sticky_piston')}
        self.sticky = {i for i in self.pistons if initial[i]['kind'] == 'sticky_piston'}
        self.cycles = []
        self.current = None
        self.last_sequence = 0

    def begin(self, cycle, snapshot):
        self.current = dict(cycle=cycle+1, ticks=0, activated=set(), extended=set(), pulled=set())
        self.observe(snapshot, 0)

    def observe(self, snapshot, step):
        if self.current is None:
            return
        current = self.current
        current['ticks'] += step
        current['snapshot'] = snapshot
        for block in snapshot['blocks']:
            if block['id'] in self.pistons and block.get('powered'):
                current['activated'].add(block['id'])
        for event in snapshot.get('events', []):
            if event['sequence'] <= self.last_sequence:
                continue
            block_id = event.get('block_id')
            if block_id in self.pistons:
                if event['kind'] == 'piston_powered':
                    current['activated'].add(block_id)
                elif event['kind'] == 'piston_extension_completed':
                    current['extended'].add(block_id)
        self.last_sequence = max((e['sequence'] for e in snapshot.get('events', [])), default=self.last_sequence)
        # 普通活塞回缩也有 pull motion；只有确实拉动方块才算回拉。
        pending = current.setdefault('pending_pulls', {})
        for motion in snapshot.get('motions', []):
            if motion['kind'] == 'pull' and motion['piston_id'] in self.sticky and motion['blocks']:
                pending[(motion['piston_id'], motion['started_at'])] = motion
        actual = {b['id']: b['position'] for b in snapshot['blocks']}
        for motion in pending.values():
            if snapshot['tick'] >= motion['completes_at'] and all(
                    actual.get(b['block_id']) == b['to'] for b in motion['blocks']):
                current['pulled'].add(motion['piston_id'])

    def end(self, complete=True):
        if self.current is None:
            return
        current = self.current
        actual = {b['id']: b['position'] for b in current['snapshot']['blocks']}
        cycle = current['cycle']
        moved = {i for i,p in self.members.items() if actual.get(i) == {**p, 'z': p['z']+cycle}}
        missing = sorted(self.members.keys()-moved)
        inactive = sorted(self.pistons-current['activated'])
        detail = dict(cycle=cycle, complete=complete, ticks=current['ticks'],
                      translation=bool(complete and not missing), activation=bool(complete and not inactive),
                      translation_fraction=len(moved)/max(1,len(self.members)),
                      activation_fraction=len(current['activated'])/max(1,len(self.pistons)),
                      extension_fraction=len(current['extended'])/max(1,len(self.pistons)),
                      unmoved=[dict(id=i, initial=self.members[i], actual=actual.get(i)) for i in missing],
                      inactive_pistons=[dict(id=i, initial=self.members[i]) for i in inactive],
                      blocks=[dict(id=i, initial=p, translated=i in moved, piston=i in self.pistons,
                                   sticky=i in self.sticky, activated=i in current['activated'],
                                   extended=i in current['extended'], pulled=i in current['pulled'])
                              for i,p in self.members.items()])
        self.cycles.append(detail)
        self.current = None

    def finish(self, result):
        if self.current is not None:
            self.end(complete=False)
        complete = len(self.cycles) == self.task['rounds'] and all(c['complete'] for c in self.cycles)
        translation = complete and all(c['translation'] for c in self.cycles)
        activation = complete and all(c['activation'] for c in self.cycles)
        accepted = translation and (activation or not self.require_activation)
        result['foundation'] = dict(protocol='whole_line_and_each_piston_v1' if self.require_activation else 'whole_line_activation_diagnostic_v2',
                                    activation_required=self.require_activation,
                                    translation=translation, activation=activation,
                                    accepted=accepted, piston_count=len(self.pistons), cycles=self.cycles)
        if result['accepted'] and not accepted:
            result['accepted'] = False
            result['reason'] = '移动线未完成每轮整线平移' if not translation else '移动线存在整轮从未激活的活塞'
