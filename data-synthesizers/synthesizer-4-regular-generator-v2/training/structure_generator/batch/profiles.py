"""十万条的厚度配额及专项条件；配额只统计实际通过的结构。"""

from ..extension_constraints import issue


def allocate(total, weights):
    """按最大余数分配整数配额，保持总量精确。"""
    denominator = sum(weights)
    values = [total * w // denominator for w in weights]
    order = sorted(range(len(weights)), key=lambda i: -(total * weights[i] % denominator))
    for i in order[:total - sum(values)]:
        values[i] += 1
    return values


def profiles(total=100000):
    result = []
    for depth, count in zip((2, 3, 4), allocate(total, (30, 30, 40))):
        cells = []

        def add(name, share, category, targets=3, density=0., dense=True, **options):
            maximum = options.pop('max_density', None)
            cells.append(dict(id=f'{depth}-{name}', name=name, share=share, depth=depth,
                              category=category, min_targets=targets, min_density=density,
                              max_density=maximum, dense=dense,
                              options=dict(search=True, simulation_budget=64, **options)))

        for label, category, shares, dense_targets in (
                ('同推', '多目标同推', (8, 8, 4), {2: 4, 3: 10, 4: 13}),
                ('推拉同推', '推拉结合同推', (6, 0, 4), {2: 6, 3: 10, 4: 13}),
                ('多时序', '推拉结合多时序', (6, 30, 4), {2: 10, 3: 13, 4: 13})):
            add(label + '常规', shares[0], category, dense=None)
            if shares[1]:
                add(label + '密集', shares[1], category, dense_targets[depth], .4)
            add(label + '稀疏', shares[2], category, dense=False, max_density=.3)
        placements = [('front', 8, 14)] if depth == 2 else (
            [('rear', 8, 14)] if depth == 3 else [('front', 4, 7), ('rear', 4, 7)])
        for placement, extension_share, saturated_share in placements:
            label = '前置' if placement == 'front' else '后置'
            add(label + '入口延伸', extension_share, '推拉结合多时序', 10, .3,
                min_extensions=1, extension_placement=placement)
            add(label + '满位延伸', saturated_share, '推拉结合多时序', 10, .35,
                min_extensions=1, extension_placement=placement, min_saturated_extensions=1)
        add('大尺寸', 8, '推拉结合多时序', 20, .35 if depth == 4 else .25,
            min_long_side=10, min_short_side=6, min_extensions=1,
            extension_placement='front' if depth == 2 else 'rear' if depth == 3 else 'any')
        for cell, quota in zip(cells, allocate(count, [c['share'] for c in cells])):
            cell['quota'] = quota
            cell['options']['simulation_budget'] = 128 if cell['name'] == '大尺寸' else 96
            result.append(cell)
    return result


def job_for(profile, index, seed):
    if profile.get('preset') == 'latest-mixed':
        from .mixed_profiles import job_for as mixed_job
        return mixed_job(profile, index, seed)
    options = dict(profile['options'])
    dense = profile['dense'] if profile['dense'] is not None else index % 3 != 0
    # 普通推拉及密集专项也倾向入口延伸；专项硬要求不受该偏好影响。
    if profile['category'] != '多目标同推' and index % 10 < 7:
        options['min_extensions'] = max(1, options.get('min_extensions', 0))
    if profile['depth'] == 3 and options.get('min_extensions'):
        options.setdefault('extension_placement', 'rear')
    return (index, seed, profile['category'], profile['depth'], dense,
            profile['min_targets'], profile['min_density'], options)


def admission(row, profile):
    """存储前独立检查专项口径，密度以整数目标和实际面积计算。"""
    if profile.get('preset') == 'latest-mixed':
        from .mixed_validation import admission as mixed_admission
        return mixed_admission(row, profile)
    c = row['coverage']
    if c['actual_depth'] != profile['depth'] or row['family'] != profile['category']:
        return '实际厚度或类别不符合专项'
    density = c['targets'] / (c['width'] * c['height'])
    if c['targets'] < profile['min_targets'] or density < profile['min_density']:
        return '实际目标数或密度不足'
    if profile['max_density'] is not None and density >= profile['max_density']:
        return '实际密度未低于稀疏上限'
    options = profile['options']
    if (max(c['width'], c['height']) < options.get('min_long_side', 0)
            or min(c['width'], c['height']) < options.get('min_short_side', 0)):
        return '实际尺寸不足'
    return issue(row['mechanisms'], options)
