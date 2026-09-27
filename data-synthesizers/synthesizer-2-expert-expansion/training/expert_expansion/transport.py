"""按预定搬运时刻检查方向性黏附与挤推集合，提前排除模块间错误牵连。"""

from .modules import xyz

DIRECTIONS=((1,0,0),(-1,0,0),(0,1,0),(0,-1,0),(0,0,1),(0,0,-1))
ADHESIVE={'slime_block','honey_block'}


def transport_valid(nodes):
    packed = [[(*xyz(b['position']), b['block']['kind']) for b in node['blocks']] for node in nodes]
    worlds = {}
    for active,node in enumerate(nodes):
        # 同一时刻的各搬运组共享同一空间状态，不必为每组重新建立。
        if node['tick'] not in worlds:
            world={}
            for index,other in enumerate(nodes):
                shift=int(other['tick']<node['tick'])
                for j,(x,y,z,kind) in enumerate(packed[index]):
                    p=(x,y,z+shift)
                    if p in world:
                        return False
                    world[p]=(index,j,kind)
            worlds[node['tick']] = world
        world = worlds[node['tick']]
        driver=node['driver']
        if node['parent'] is not None:
            driver=(driver[0],driver[1],driver[2]+1)
        queue=[xyz(node['anchor'])];included=set()
        while queue:
            p=queue.pop()
            if p in included or p not in world:
                continue
            index,j,kind=world[p]
            if index!=active:
                return False
            included.add(p)
            if len(included)>12:
                return False
            queue.append((p[0],p[1],p[2]+1))
            if kind in ADHESIVE:
                for vector in DIRECTIONS:
                    q=(p[0]+vector[0],p[1]+vector[1],p[2]+vector[2])
                    other=world.get(q)
                    if not other or q==driver or other[2]=='light_blue_glazed_terracotta':
                        continue
                    if {kind,other[2]}==ADHESIVE:
                        continue
                    # 同刻分支可能已开始运动，侧向不再黏附；正面挤推仍会检查。
                    # 此处保留可能可行的连接，实际动作先后交给完整模拟判定。
                    if other[0] != active and nodes[other[0]]['tick'] == node['tick']:
                        continue
                    queue.append(q)
        if len(included)!=len(node['blocks']):
            return False
    return True
