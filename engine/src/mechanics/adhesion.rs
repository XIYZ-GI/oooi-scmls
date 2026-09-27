use crate::types::BlockKind;

pub fn blocks_stick(source: BlockKind, target: BlockKind) -> bool {
    if !source.is_adhesive() {
        return false;
    }
    if target == BlockKind::LightBlueGlazedTerracotta {
        return false;
    }
    if matches!(
        (source, target),
        (BlockKind::SlimeBlock, BlockKind::HoneyBlock)
            | (BlockKind::HoneyBlock, BlockKind::SlimeBlock)
    ) {
        return false;
    }
    true
}

#[cfg(test)]
mod tests {
    use super::blocks_stick;
    use crate::types::BlockKind;

    #[test]
    fn slime_and_honey_do_not_stick_to_each_other() {
        assert!(!blocks_stick(BlockKind::SlimeBlock, BlockKind::HoneyBlock));
        assert!(!blocks_stick(BlockKind::HoneyBlock, BlockKind::SlimeBlock));
    }

    #[test]
    fn adhesive_blocks_do_not_stick_to_glazed_terracotta() {
        assert!(!blocks_stick(
            BlockKind::SlimeBlock,
            BlockKind::LightBlueGlazedTerracotta
        ));
    }
}
