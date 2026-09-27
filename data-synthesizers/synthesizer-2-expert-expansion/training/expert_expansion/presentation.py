"""将已构造的机械结构放到不同网格位置，保留真实厚度与允许厚度差别。"""

from copy import deepcopy

from ..compact.transforms import transform
from ..serialization import digest


def variants(row, rng):
    for mode in range(3):
        copy=transform(row,swap=rng.choice((False,True)),sx=rng.choice((-1,1)),sy=rng.choice((-1,1)),materials=False) if mode else deepcopy(row)
        task=copy['task']
        if mode:
            left,right,bottom,top=[rng.randrange(4) for _ in range(4)]
            # 覆盖网页常见7×5以及非居中摆放，不把机械外接框当作输入尺寸。
            if mode==2:
                right+=max(0,7-task['width']-left-right)
                top+=max(0,5-task['height']-bottom-top)
            width=task['width']+left+right;height=task['height']+bottom+top
            depth=task['depth']+(rng.choice((0,0,1,2)) if mode==2 else 0)
            if width*height*depth<=512 and max(width,height)<=24:
                for p in [*[b['position'] for b in copy['proposal']['blocks']],copy['proposal']['push'],*task['targets']]:
                    p['x']+=left;p['y']+=bottom
                task.update(width=width,height=height,depth=depth)
        copy['presentation']=mode
        copy['proposal']['blocks'].sort(key=lambda b:tuple(b['position'][a] for a in ('x','y','z')))
        copy['id']=digest([task,copy['proposal']])[:24]
        yield copy
