"""五万条新机制混合批次：厚度、实际尺寸、密度与功能的独立配额。"""

from .profiles import allocate


PRESET = 'latest-mixed'
SIZE_BANDS = {
    '小尺寸': dict(min_side=2, min_long=3, max_long=6,
                  sections=((5, 5), (6, 5), (6, 6))),
    '中尺寸': dict(min_side=4, min_long=7, max_long=9,
                  sections=((7, 5), (7, 6), (7, 7), (8, 6), (8, 7), (8, 8), (9, 7))),
    '较大尺寸': dict(min_side=5, min_long=10, max_long=16,
                    sections=((10, 6), (10, 8), (12, 8), (12, 10), (14, 8), (16, 8))),
    '中小混合': dict(min_side=3, min_long=4, max_long=9,
                    sections=((5, 5), (6, 5), (6, 6), (7, 6), (7, 7), (8, 7), (8, 8))),
}
DENSITY_BANDS = {'稀疏': (0., .3), '适中': (.3, .5), '密集': (.5, None),
                 '高密度联合': (.72, None), '不限密度': (0., None)}
MECHANISMS = {'跨线红石供电': 'next_source', '红石回拉': 'redstone_recall',
              '半动机': 'half_engine'}


def profiles(total=50000):
    result = []
    for depth, count in zip((3, 4, 5, 6), allocate(total, (1, 1, 1, 1))):
        cells = []

        def add(label, weight, size, density, category='推拉结合多时序',
                groups=2, mechanism=None, rectangle=None, combined=False):
            lo, hi = DENSITY_BANDS[density]
            size_rule = SIZE_BANDS[size]
            requirements = dict(size=size, density=density, min_groups=groups,
                                mechanism=mechanism, rectangle=rectangle, combined=combined)
            options = dict(search=True, simulation_budget=512 if depth >= 4 else 192,
                           branch_attempts=60 if depth >= 4 else 30,
                           edit_budget=6000 if depth >= 4 else 600,
                           front_only=True, diverse_batch=requirements,
                           min_long_side=size_rule['min_long'],
                           min_short_side=size_rule['min_side'],
                           prune_completion=False)
            if depth >= 4:
                options.update(regular=True, layered=True, depth=depth, front_layers=depth-1,
                               section_sizes=size_rule['sections'], completion_rounds=1)
            if mechanism or rectangle and depth == 4:
                kinds = tuple(MECHANISMS.values()) if mechanism in (None, '组合') else (mechanism,)
                options.update(feedback_growth=True, feedback_kinds=kinds,
                               feedback_minimum=2 if mechanism == '组合' else 1,
                               feedback_maximum=2, feedback_attempts=400,
                               feedback_continuation=4)
            if rectangle and depth == 4:
                options['rectangular_seed'] = True
            if combined:
                options.update(min_groups=4, min_simultaneous=11,
                               min_solid_area=11, max_empty_area=4)
            cells.append(dict(id=f'{depth}-{label}', name=label, preset=PRESET,
                              share=weight, depth=depth, category=category,
                              min_targets=11 if rectangle or combined else 3,
                              min_density=lo, max_density=hi,
                              dense=density != '稀疏', requirements=requirements, options=options))

        for size in ('小尺寸', '中尺寸'):
            add('同推稀疏'+size, 5, size, '稀疏', '多目标同推', 1)
            add('同推密集'+size, 7, size, '密集', '多目标同推', 1)
        add('推拉同推', 6, '中小混合', '不限密度', '推拉结合同推', 1)
        add('多时序稀疏中尺寸', 8, '中尺寸', '稀疏')
        add('多时序稀疏较大尺寸', 5, '较大尺寸', '稀疏')
        add('多时序适中小尺寸', 8, '小尺寸', '适中')
        add('多时序适中中尺寸', 10, '中尺寸', '适中')
        add('多时序密集小尺寸', 8, '小尺寸', '密集')
        add('多时序密集中尺寸', 8, '中尺寸', '密集')
        add('复杂时序较大尺寸', 4, '较大尺寸', '不限密度', groups=3 if depth == 3 else 4)
        add('同推实心矩形', 8, '中小混合', '不限密度',
            '多目标同推' if depth == 3 else '推拉结合多时序',
            1 if depth == 3 else 2, rectangle='simultaneous')
        if depth >= 4:
            for label, kind in MECHANISMS.items():
                add(label, 8, '中小混合', '不限密度', mechanism=kind)
            add('红石与半动机组合', 4, '中小混合', '不限密度', mechanism='组合')
            add('矩形内多时序', 3, '中小混合', '不限密度', rectangle='partitioned')
            add('高密度复杂联合', 2, '中小混合', '高密度联合', groups=4,
                rectangle='either', combined=True)
        for cell, quota in zip(cells, allocate(count, [p['share'] for p in cells])):
            cell['quota'] = quota
            result.append(cell)
    # 本批停用已尝试超过一千次且零产出的专项，保留其余原始配额。
    excluded = ('3-同推实心矩形', '3-同推密集中尺寸', '3-同推密集小尺寸', '3-推拉同推', '4-同推密集中尺寸', '4-同推稀疏小尺寸', '4-推拉同推', '5-同推密集中尺寸', '5-同推密集小尺寸', '5-推拉同推', '6-推拉同推')
    return [cell for cell in result if cell['id'] not in excluded]


def job_for(profile, index, seed):
    options = dict(profile['options'])
    # 小矩形路线随机选择供电端；不读取人工成品，也不复制历史候选。
    if options.get('rectangular_seed'):
        options['fan_end_observers'] = index % 2 == 0
    return (index, seed, profile['category'], profile['depth'], profile['dense'],
            profile['min_targets'], profile['min_density'], options)
