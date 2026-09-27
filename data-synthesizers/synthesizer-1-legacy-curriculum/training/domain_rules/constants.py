"""用户确认的设计禁忌及方向约定。"""

RULE = 'piston_observer_detection_face_v1'
REASON = '设计禁忌：活塞直接朝观察者侦测端推动'
VECTORS = {
    'positive_x': (1, 0, 0), 'negative_x': (-1, 0, 0),
    'positive_y': (0, 1, 0), 'negative_y': (0, -1, 0),
    'positive_z': (0, 0, 1), 'negative_z': (0, 0, -1),
}
AXES = ('x', 'y', 'z')
