//! 航械设计禁忌：活塞直接朝观察者侦测端推动。
//!
//! 对应 `training/domain_rules/observer.py`，不改变引擎物理，只做输入与运行时判定。

use std::collections::HashMap;

use crate::model::{BlockEntry, Point, Proposal};
use crate::protocol::{RULE, RULE_REASON};

/// 朝向名到单位向量的映射，与 Python 侧 `VECTORS` 一致。
fn vector(facing: &str) -> Option<(i32, i32, i32)> {
    Some(match facing {
        "positive_x" => (1, 0, 0),
        "negative_x" => (-1, 0, 0),
        "positive_y" => (0, 1, 0),
        "negative_y" => (0, -1, 0),
        "positive_z" => (0, 0, 1),
        "negative_z" => (0, 0, -1),
        _ => return None,
    })
}

/// 一条禁忌记录。
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Issue {
    pub rule: &'static str,
    pub piston: Point,
    pub observer: Point,
    pub facing: String,
    pub origin: &'static str,
    pub air_gap: i32,
    pub evidence: &'static str,
    pub tick: Option<u64>,
}

impl Issue {
    /// 转成与 Python 侧同形的 JSON，便于两边直接比对。
    pub fn to_json(&self) -> serde_json::Value {
        let mut value = serde_json::json!({
            "rule": self.rule,
            "piston": {"x": self.piston.x, "y": self.piston.y, "z": self.piston.z},
            "observer": {"x": self.observer.x, "y": self.observer.y, "z": self.observer.z},
            "facing": self.facing,
            "origin": self.origin,
            "air_gap": self.air_gap,
            "evidence": self.evidence,
        });
        if let Some(tick) = self.tick {
            value["tick"] = serde_json::json!(tick);
        }
        value
    }
}

/// 判断一批方块里是否存在活塞直接顶推观察者侦测端的布局。
///
/// `external` 是外部推动器位置；`distances` 控制检查相邻与隔一格两档。
pub fn layout_issues(
    blocks: &[BlockEntry],
    external: Option<Point>,
    distances: &[i32],
    origin_of_external: &'static str,
) -> Vec<Issue> {
    // 坐标到方块种类与朝向的映射；重复坐标取后者，与 Python 字典赋值语义一致。
    let mut placed: HashMap<Point, &str> = HashMap::new();
    let mut facing_of: HashMap<Point, &str> = HashMap::new();
    for entry in blocks {
        placed.insert(entry.position, entry.block.kind.as_str());
        // 朝向字段缺省时按 positive_z 处理，与 Python 的 `block.get('facing', ...)` 一致。
        let facing = if entry.block.facing.is_empty() {
            "positive_z"
        } else {
            entry.block.facing.as_str()
        };
        facing_of.insert(entry.position, facing);
    }

    // 待检查的活塞：结构内部的所有活塞，加上可选的外部推动器。
    let mut pistons: Vec<(Point, &str, &'static str)> = blocks
        .iter()
        .filter(|entry| entry.block.kind == "piston" || entry.block.kind == "sticky_piston")
        .map(|entry| {
            let facing = if entry.block.facing.is_empty() {
                "positive_z"
            } else {
                entry.block.facing.as_str()
            };
            (entry.position, facing, "internal")
        })
        .collect();
    if let Some(point) = external {
        pistons.push((point, "positive_z", origin_of_external));
    }

    let mut issues = Vec::new();
    for (position, facing, origin) in pistons {
        let Some(direction) = vector(facing) else {
            continue;
        };
        for distance in distances {
            let front = Point::new(
                position.x + distance * direction.0,
                position.y + distance * direction.1,
                position.z + distance * direction.2,
            );
            let Some(kind) = placed.get(&front) else {
                continue;
            };
            if *kind == "air" {
                continue;
            }
            // 观察者 facing 是输出端；同向活塞从其反侧接触的正是侦测端。
            if *kind == "observer" && facing_of.get(&front) == Some(&facing) {
                issues.push(Issue {
                    rule: RULE,
                    piston: position,
                    observer: front,
                    facing: facing.to_string(),
                    origin,
                    air_gap: distance - 1,
                    evidence: if *distance == 1 {
                        "adjacent"
                    } else {
                        "one_air_gap_risk"
                    },
                    tick: None,
                });
            }
            // 前方已有其他方块时，不把隔着它的观察者算成直接顶推。
            break;
        }
    }
    issues
}

/// 检查候选结构本身；外部推动器在推动点后方一格。
pub fn proposal_issues(proposal: &Proposal) -> Vec<Issue> {
    let external = Point::new(proposal.push.x, proposal.push.y, proposal.push.z - 1);
    layout_issues(&proposal.blocks, Some(external), &[1, 2], "external")
}

/// 只检查实际发生的推出，排除粘性活塞回拉和旁侧黏附带动。
///
/// `blocks` 与 `motions` 取自引擎快照。
pub fn snapshot_issues(
    blocks: &[BlockEntry],
    motions: &[(i64, String, Point)],
    tick: u64,
) -> Vec<Issue> {
    // 只检查实际发生的推出动作。
    let mut issues = Vec::new();
    let mut direct: Option<Vec<Issue>> = None;
    for (piston_id, kind, piston_position) in motions {
        let _ = piston_id;
        if kind != "push" {
            continue;
        }
        let cache = direct.get_or_insert_with(|| layout_issues(blocks, None, &[1], "internal"));
        for issue in cache.iter() {
            if issue.piston == *piston_position {
                let mut issue = issue.clone();
                issue.evidence = "runtime_push";
                issue.tick = Some(tick);
                issues.push(issue);
            }
        }
    }
    issues
}

/// 领域规则的统一失败文案。
pub fn reason() -> &'static str {
    RULE_REASON
}
