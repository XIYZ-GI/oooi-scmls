"""将已保存的失败需求与候选整理为中文查看索引。"""


def render_report(records, checkpoint):
    lines = [
        '# 第三阶段失败结构查看索引', '',
        '网页“服务器结构”中搜索“阶段3失败”，编号与下表一致。每个不同候选均有“本体”和“十负载装配”两版。候选编号沿用原评估编号，重复输出合并，所以编号可能不连续。', '',
        '这些结构是最终模型的原始输出，没有修补或重新生成。人工样本需求表示让模型重新完成人工成品对应的需求，失败不表示人工成品有问题。', '',
        '共11条失败评估记录：新几何1条、历史能力检查6条、厚度对照4条。11个任务编号不同，其中厚度对照包含同一布局的不同厚度要求。', '',
        '“未完成负载”是评估器的失败判定，不能据此断言所有目标都没动，也不能当作具体机械故障原因；“时序不符”表示目标完成先后或同时性不符合要求。所有候选均在第一轮未通过。', '',
        '装配版保留原候选和目标负载，另放置一个朝正Z方向的外部活塞；不预放启动红石块。每个目标沿正Z放10块铁块，首块坐标以需求为准。要按原评估触发，在外部活塞后方放红石块，第4游戏刻移除；普通网页持续供电播放不等同于原评估协议。', '',
        '原评估要求每轮所有负载前进一格、满足时序、移动线整体前进一格，连续3轮。时限是每轮时限。完整任务、候选判定和服务器结构编号保存在 `data/generation/stage3-complete/failures/index.json`。', '',
        f'模型SHA256：`{checkpoint}`。', '',
        '| 编号 | 来源 | 截面 | 目标数 | 时序组数 | 厚度上限 | 不同候选 | 判定 |',
        '| --- | --- | --- | --- | --- | --- | --- | --- |',
    ]
    for record in records:
        task = record['task']
        reasons = '、'.join(sorted({c['reason_short'] for c in record['candidates']}))
        lines.append(f"| {record['number']:02d} | {record['label']} | {task['width']}×{task['height']} | "
                     f"{len(task['targets'])} | {len({t['order'] for t in task['targets']})} | "
                     f"{task['depth']} | {len(record['candidates'])} | {reasons} |")
    lines += ['', '5目标厚度对照的同一布局已有两格成功解，但允许3格、4格时这些候选失败；10目标对照允许4格时成功，允许2格、3格时失败。模型未生成成功结构不等于需求无解。']
    for record in records:
        task = record['task']
        lines += ['', f"## {record['number']:02d} · {record['label']}", '',
                  f"任务编号：`{record['task_id']}`；每轮{task['max_ticks']}游戏刻，共{task['rounds']}轮。", '',
                  '以下坐标为每个目标第一块负载的位置，按要求的推动次序分组：', '']
        for order in sorted({t['order'] for t in task['targets']}):
            points = '、'.join(f"({t['x']}, {t['y']}, {t['z']})" for t in task['targets'] if t['order'] == order)
            lines.append(f'- 第{order}组：{points}')
        lines += ['', '| 候选 | 合并的原候选编号 | 推动点（移动线方块） | 外部活塞 | 启动红石块 | 原判定 |',
                  '| --- | --- | --- | --- | --- | --- |']
        for candidate in record['candidates']:
            push = candidate['proposal']['push']
            p = tuple(push[a] for a in ('x', 'y', 'z'))
            actuator = (*p[:2], p[2]-1)
            power = (*p[:2], p[2]-2)
            lines.append(f"| {candidate['number']} | {','.join(map(str, candidate['original_candidates']))} | "
                         f"{p} | {actuator} | {power} | {candidate['evaluation']['reason']} |")
    return '\n'.join(lines)+'\n'
