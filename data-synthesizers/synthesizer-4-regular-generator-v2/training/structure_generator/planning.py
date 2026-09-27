"""把目标数量、尺寸和入口延伸偏好落实为功能分支需求。"""

from .requests import requirements


def plan(rng, category, depth, dense, options):
    if depth > 4:
        from .multilayer_plan import request
        return request(rng, depth, category)
    target = options.get('target_goal', 3)
    large = options.get('min_long_side', 0) >= 10
    request = requirements(rng, category, depth, dense)
    if depth == 4 and dense:
        wide = target >= 13 and (category != '推拉结合多时序' or large or target >= 20)
        count = rng.choice((3, 4) if wide else (2, 3))
        leaf = lambda: dict(outputs=(3 if target >= 13 else 2, 7), children=[])
        children = []
        delayed = rng.randrange(count)
        for i in range(count):
            child = leaf()
            if category == '推拉结合同推':
                child = dict(outputs=(0, 0), children=[('pull', leaf())])
            elif category == '推拉结合多时序' and (i == delayed or rng.random() < .35):
                child = dict(outputs=(2, 5), children=[('pull', leaf())])
                if large or target >= 20:
                    child['children'][0][1]['children'] = [('pull', leaf())]
            children.append(('push',child))
        request = dict(outputs=(0,0),children=children)
    if depth in (2,3) and (dense or target >= 9 or options.get('min_long_side',0) >= 8):
        from .thin_planning import plan as thin_plan
        request = thin_plan(rng,category,depth,options)
        if category != '多目标同推':
            request['pull_offset'] = 1 if depth == 2 else 0
    candidates = []
    def visit(node):
        if any(kind == 'pull' for kind,_ in node['children']):
            candidates.append(node)
        for _, child in node['children']:
            visit(child)
    visit(request)
    if candidates and options.get('min_extensions',0):
        rng.shuffle(candidates)
        placement = options.get('extension_placement','any')
        if placement in ('front','rear') and request in candidates:
            candidates.remove(request)
            candidates.insert(0,request)
        for node in candidates[:options['min_extensions']]:
            node['extension'] = True
            if placement != 'any':
                node['pull_offset'] = 1 if placement == 'front' else 0
            if options.get('min_saturated_extensions',0):
                node['outputs'] = (4,max(4,node['outputs'][1]))
    return request
