"""将一次随机供电生长限制在所属双层内，不靠增加厚度容纳连接。"""

from .growth import supply as original_supply
from .side_growth import supply as side_supply


def supply(layout, rng, request, anchor, tick):
    start = request['layer']
    previous = getattr(layout, 'placing_layers', None)
    layout.placing_layers = (start, start+1)
    try:
        if request.get('rectangular_fan'):
            from .layered_fan_supply import supply as fan_supply
            return fan_supply(layout, rng, anchor, request)
        if request.get('dense_strip'):
            from .layered_dense_supply import supply as dense_supply
            layout.placing_layers = (start-1, start+1)
            return dense_supply(layout, rng, anchor, axis=request.get('dense_axis'))
        if request.get('solid_strip'):
            from .layered_strip import supply as strip_supply
            return strip_supply(layout, rng, anchor)
        if request.get('return_supply'):
            from .layered_return_supply import supply as return_supply
            return return_supply(layout, rng, anchor)
        if anchor[2] == start+1:
            # 五格的最前组从前片接入，供电沿侧面展开，不能再占用第六格。
            return original_supply(layout, rng, anchor, '共享供电片', budget=8, compact=True)
        kinds = {kind for kind, _ in request['children']}
        if kinds == {'push', 'pull'} or request.get('mixed_supply'):
            from .layered_root import supply as root_supply
            return root_supply(layout, rng, anchor, request)
        if request.get('relay_only'):
            return original_supply(layout, rng, anchor, '共享供电片', budget=8, compact=True)
        if kinds == {'pull'}:
            if start >= 2 and request.get('pull_offset') == 0:
                from .layered_strip import supply as strip_supply
                return strip_supply(layout, rng, anchor, width_limit=2)
            if start >= 2 and rng.random() < .8:
                from .layered_mixed_strip import supply as mixed_strip
                return mixed_strip(layout, rng, anchor)
            return side_supply(layout, rng, anchor, budget=8)
        if start >= 2 and not kinds:
            if rng.random() < .65:
                from .layered_strip import supply as strip_supply
                return strip_supply(layout, rng, anchor)
            if rng.random() < .5:
                return side_supply(layout, rng, anchor, budget=8)
        return original_supply(layout, rng, anchor, '共享供电片', budget=8, compact=True)
    finally:
        layout.placing_layers = previous
