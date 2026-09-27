"""聚合真实覆盖；进度查询不加载十万条完整结构。"""

from datetime import datetime, timezone
import shutil

from ...serialization import write_json


def dimensions(row):
    c, m = row['coverage'], row['mechanisms']
    density = c['targets'] / (c['width'] * c['height'])
    values = dict(depth=str(c['actual_depth']), category=row['family'],
                  timing=str(c['groups']), targets=str(c['targets']),
                  sizes=f"{min(c['width'], c['height'])}×{max(c['width'], c['height'])}",
                  density='至少0.5' if density >= .5 else '0.4至0.5' if density >= .4
                  else '0.3至0.4' if density >= .3 else '低于0.3')
    for key, value in values.items():
        yield key, value
    for key in ('extended_input_pulls', 'saturated_extension_pulls', 'shared_input_charges'):
        if m.get(key, 0):
            yield 'mechanisms', key
    for key, value in m.get('extension_placements', {}).items():
        if value:
            yield 'extension_placements', key
    yield 'depth_timing_density', f"{c['actual_depth']}格/{c['groups']}时序/{values['density']}"
    metrics = row.get('batch_metrics')
    if metrics:
        yield 'size_band', metrics['size_band']
        yield 'density_band', metrics['density_band']
        actual = metrics['compactness']['target_density']
        yield 'actual_density_band', ('稀疏' if actual < .3 else '适中' if actual < .5
                                     else '密集' if actual < .72 else '高密度')
        for kind in metrics['verified_mechanisms']:
            yield 'verified_feedback', kind
            yield 'depth_feedback', f"{c['actual_depth']}格/{kind}"
        if metrics['simultaneous_rectangle'] >= 12 and metrics['max_simultaneous'] >= 11:
            yield 'solid_rectangles', '十二点以上同刻矩形'
        if metrics['partitioned_rectangle'] >= 12 and metrics['max_simultaneous'] >= 11:
            yield 'solid_rectangles', '十二点以上分时序矩形'


def report(repo, status, **extra):
    repo.db.commit()
    stats = repo.stats()
    coverage = {}
    for dimension, value, count in repo.db.execute('SELECT dimension,value,count FROM coverage'):
        coverage.setdefault(dimension, {})[value] = count
    cells = [dict(**p, **stats[p['id']]) for p in repo.profiles]
    value = dict(status=status, updated_at=datetime.now(timezone.utc).isoformat(),
                 target=sum(p['quota'] for p in repo.profiles),
                 accepted=sum(s['accepted'] for s in stats.values()),
                 attempts=sum(s['attempts'] for s in stats.values()),
                 worker_cpu_seconds=sum(s['cpu_seconds'] for s in stats.values()),
                 pending=repo.db.execute('SELECT COUNT(*) FROM pending').fetchone()[0],
                 quarantined_errors=repo.db.execute('SELECT COUNT(*) FROM errors').fetchone()[0],
                 consecutive_errors=repo.consecutive_errors(),
                 recent_errors=[dict(index=i, profile=p, kind=k, message=m, created_at=t)
                                for i,p,k,m,t in repo.db.execute('''SELECT id,profile,
                                    json_extract(body,'$.kind'),json_extract(body,'$.message'),created_at
                                    FROM errors ORDER BY created_at DESC,id DESC LIMIT 3''')],
                 free_disk_gib=round(shutil.disk_usage(repo.directory).free / 2**30, 2),
                 profiles=cells, coverage=coverage,
                 reasons=dict(repo.db.execute('SELECT reason,SUM(count) FROM reasons GROUP BY reason')),
                 **extra)
    value['unfilled_profiles'] = [dict(id=p['id'], remaining=p['quota']-p['accepted'],
                                      attempts=p['attempts']) for p in cells if p['accepted'] < p['quota']]
    write_json(repo.directory / 'progress.json', value)
    return value
