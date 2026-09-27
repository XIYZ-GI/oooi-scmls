"""按完整支路组合预筛，允许同刻邻组接齐后共同接受物理验证。"""


def extend_wave(search, links, tick, attempts=12):
    """临时装配期间保留全部输出要求；整组失败则恢复原样，不作为候选通过。"""
    saved = search.layout.checkpoint()
    for _ in range(attempts):
        if (search.simulations >= search.options.get('simulation_budget', 48)
                or search.edits >= search.options.get('edit_budget', 180)):
            break
        search.layout.restore(saved)
        assembled = True
        for kind, child, driver, entry in links:
            search.layout.links.append(dict(kind=kind, driver=driver, entry=entry, tick=tick))
            if not search.extend(child, entry, tick+(8 if kind == 'pull' else 4),
                                 defer_validation=True):
                assembled = False
                break
        if assembled and search.valid():
            return True
    search.layout.restore(saved)
    return False
