"""同时求解空间占位、接口连接和分支时序，完整模拟才决定验收。"""

from collections import defaultdict
import time

from ortools.sat.python import cp_model

from ..evaluator import evaluate
from .modules import xyz
from .candidate_cache import candidates
from .connections import add_conflicts
from .signals import constrain_outputs
from .spatial_constraints import constrain_space
from .reduce_candidates import reduce_candidates


def solve(task, modules, seconds=300, limit=100, search_depth=None):
    started = time.monotonic()
    nodes = reduce_candidates(task, candidates(task, modules))
    if search_depth is not None:
        if not 1 <= search_depth <= task['depth']:
            raise ValueError('搜索厚度必须在原需求的允许范围内')
        nodes = [n for n in nodes if all(b['position']['z'] >= -search_depth-1 for b in n['blocks'])]
        nodes = reduce_candidates(task,nodes)
    print({'局部放置数': len(nodes)}, flush=True)
    model = cp_model.CpModel()
    choose = [model.new_bool_var(f'n{i}') for i in range(len(nodes))]
    at, occupy, targets, incoming = defaultdict(list), defaultdict(list), defaultdict(list), defaultdict(list)
    for i, n in enumerate(nodes):
        at[xyz(n['anchor'])].append(i)
        for b in n['blocks']:
            occupy[xyz(b['position'])].append(i)
        for t in n['covered']:
            targets[t].append(i)
        for c in n['children']:
            incoming[xyz(c['anchor'])].append(i)
    points = set(at) | set(incoming)
    roots = {p: model.new_bool_var(f'r{p}') for p in points}
    clock = {p: model.new_int_var(0, 96, f't{p}') for p in points}
    group_time = [model.new_int_var(6, 102, f'g{i}') for i in range(max(t['order'] for t in task['targets']))]
    for earlier, later in zip(group_time, group_time[1:]):
        model.add(earlier < later)
    model.add(sum(roots.values()) == 1)
    model.add(sum(choose) <= max(12, len(task['targets'])))
    for indices in occupy.values():
        model.add_at_most_one([choose[i] for i in indices])
    for i in range(len(task['targets'])):
        model.add(sum(choose[j] for j in targets[i]) == 1)
    for p in points:
        model.add(sum(choose[i] for i in at[p]) == roots[p]+sum(choose[i] for i in incoming[p]))
        model.add(clock[p] == 0).only_enforce_if(roots[p])
        # 外部推动点必须从后面可以接触，外部装置也不能占用已有方块。
        behind = set(i for q, indices in occupy.items() if q[:2] == p[:2] and q[2] < p[2] for i in indices)
        for i in behind:
            model.add(choose[i] == 0).only_enforce_if(roots[p])
    for i, n in enumerate(nodes):
        t = clock[xyz(n['anchor'])]
        for c in n['children']:
            model.add(clock[xyz(c['anchor'])] == t+c['delay']).only_enforce_if(choose[i])
    constrain_outputs(model, choose, clock, group_time, nodes, task)
    print({'供电约束': '完成'},flush=True)
    constrain_space(model, choose, clock, nodes)
    print({'运动边界约束': '完成'},flush=True)
    priority = sorted(range(len(nodes)),key=lambda i:(
        min((len(targets[t]) for t in nodes[i]['covered']),default=len(nodes)+1),
        -len(nodes[i]['covered']),-len(nodes[i]['children']),len(nodes[i]['blocks']),nodes[i]['key']))
    model.add_decision_strategy([choose[i] for i in priority],cp_model.CHOOSE_FIRST,cp_model.SELECT_MAX_VALUE)
    solver = cp_model.CpSolver()
    solver.parameters.num_search_workers = 2
    solver.parameters.random_seed = 20260922
    solver.parameters.repair_hint = False
    solver.parameters.cp_model_probing_level = 0
    solver.parameters.symmetry_level = 0
    solver.parameters.max_presolve_iterations = 2
    solver.parameters.presolve_substitution_level = 0
    solver.parameters.search_branching = cp_model.PARTIAL_FIXED_SEARCH
    failures = []
    answer = None
    status = None
    for attempt in range(limit):
        remaining = seconds-(time.monotonic()-started)
        if remaining <= 0:
            break
        solver.parameters.max_time_in_seconds = remaining
        status = solver.solve(model)
        if status not in (cp_model.FEASIBLE, cp_model.OPTIMAL):
            break
        selected = [i for i in range(len(nodes)) if solver.value(choose[i])]
        stamps = {p: solver.value(t) for p,t in clock.items()}
        # 保留当前大部分已满足的连接，下一次仅修正新增约束冲突。
        model.clear_hints()
        for variable in [*choose,*roots.values(),*clock.values(),*group_time]:
            model.add_hint(variable,solver.value(variable))
        conflicts = add_conflicts(model, choose, clock, nodes, selected, stamps)
        if conflicts:
            failures.append(dict(reason='连接图运行边界冲突', conflicts=conflicts,
                                 nodes=[nodes[i]['key'] for i in selected]))
            print({'候选': attempt+1, '错误牵连连接': conflicts}, flush=True)
            continue
        p = next(p for p in points if solver.value(roots[p]))
        proposal = dict(blocks=[b for i in selected for b in nodes[i]['blocks']], push=dict(zip(('x','y','z'),p)))
        value = evaluate(task, proposal, foundation=True, feedback=True, require_activation=False)
        print({'候选': attempt+1, '单元': len(selected), '通过': value['accepted'], '原因': value['reason']}, flush=True)
        if value['accepted']:
            answer = dict(task=task, proposal=proposal, evaluation=value,
                          assembly_method='constraint_solver_v2',
                          modules=[dict(id=nodes[i]['module'], placement_key=nodes[i]['key'],anchor=nodes[i]['anchor'],
                                        targets=nodes[i]['covered'],
                                        start=solver.value(clock[xyz(nodes[i]['anchor'])]),
                                        connections=nodes[i]['children']) for i in selected])
            break
        failures.append(dict(reason=value['reason'], nodes=[nodes[i]['key'] for i in selected],
                             proposal=proposal, evaluation=value))
        model.add(sum(choose[i] for i in selected) < len(selected))
    return dict(accepted=answer is not None, solution=answer, seconds=time.monotonic()-started,
                search_depth=search_depth or task['depth'],
                placed_options=len(nodes), complete_proposals=len(failures)+int(answer is not None),
                status=solver.status_name(status) if status is not None else 'TIME_LIMIT', failures=failures,
                note='CP-SAT按目标、局部供电结构、空间接口及分支时序装配；没有读取专家成品、专家身份或装配配方。完整模拟为最终判定。')
