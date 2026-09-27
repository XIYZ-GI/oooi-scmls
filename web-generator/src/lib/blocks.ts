import type { BlockKind, Direction } from '@/types'

export interface BlockDefinition {
  kind: BlockKind
  label: string
  description: string
  texture: string
  directional: boolean
  tint: string
}

// 页面位于 WebViewAssetLoader 的 /assets/www/ 下，贴图必须使用相对路径。
const texture = (name: string) => `${import.meta.env.BASE_URL}textures/blocks/${name}.png`

export const BLOCKS: BlockDefinition[] = [
  {
    kind: 'slime_block',
    label: '黏液块',
    description: '黏附除蜂蜜块、带釉陶瓦和活塞臂外的六面方块',
    texture: texture('slime'),
    directional: false,
    tint: '#68A57A',
  },
  {
    kind: 'honey_block',
    label: '蜂蜜块',
    description: '黏附除黏液块、带釉陶瓦和活塞臂外的六面方块',
    texture: texture('honey_side'),
    directional: false,
    tint: '#C69542',
  },
  {
    kind: 'piston',
    label: '活塞',
    description: '收到信号后延迟伸出，最多推动十二个方块',
    texture: texture('piston_top_normal'),
    directional: true,
    tint: '#9A8B6A',
  },
  {
    kind: 'sticky_piston',
    label: '粘性活塞',
    description: '收回完成时尝试拉回前方方块',
    texture: texture('piston_top_sticky'),
    directional: true,
    tint: '#789267',
  },
  {
    kind: 'redstone_block',
    label: '红石块',
    description: '向相邻六面持续发出普通红石信号',
    texture: texture('redstone_block'),
    directional: false,
    tint: '#B33B38',
  },
  {
    kind: 'observer',
    label: '观察者',
    description: '观察端检测更新，输出端延迟发出强充能脉冲',
    texture: texture('observer_front'),
    directional: true,
    tint: '#6F7476',
  },
  {
    kind: 'iron_block',
    label: '铁块',
    description: '可黏附、可推拉并可被强充能',
    texture: texture('iron_block'),
    directional: false,
    tint: '#C9D1D2',
  },
  {
    kind: 'light_blue_glazed_terracotta',
    label: '淡蓝色带釉陶瓦',
    description: '不被黏附、可推动、不可拉回并可被强充能',
    texture: texture('glazed_terracotta_light_blue'),
    directional: true,
    tint: '#63AFC2',
  },
  {
    kind: 'glass',
    label: '玻璃',
    description: '可黏附、可推拉，但不能被强充能',
    texture: texture('glass'),
    directional: false,
    tint: '#B8D6DB',
  },
]

export const BLOCK_BY_KIND = Object.fromEntries(
  BLOCKS.map((block) => [block.kind, block]),
) as Record<BlockKind, BlockDefinition>

export const DIRECTIONS: Array<{ value: Direction; label: string }> = [
  { value: 'positive_x', label: '+X' },
  { value: 'negative_x', label: '-X' },
  { value: 'positive_y', label: '+Y' },
  { value: 'negative_y', label: '-Y' },
  { value: 'positive_z', label: '+Z' },
  { value: 'negative_z', label: '-Z' },
]

export function blockTextures(kind: BlockKind, observerLit = false): string[] {
  const all = (name: string) => Array<string>(6).fill(texture(name))
  switch (kind) {
    case 'honey_block':
      return [
        texture('honey_side'),
        texture('honey_side'),
        texture('honey_top'),
        texture('honey_bottom'),
        texture('honey_side'),
        texture('honey_side'),
      ]
    case 'piston':
    case 'sticky_piston':
      return [
        texture('piston_side'),
        texture('piston_side'),
        texture('piston_side'),
        texture('piston_side'),
        texture(kind === 'sticky_piston' ? 'piston_top_sticky' : 'piston_top_normal'),
        texture('piston_bottom'),
      ]
    case 'observer':
      return [
        texture('observer_side'),
        texture('observer_side'),
        texture('observer_top'),
        texture('observer_top'),
        texture('observer_front'),
        texture(observerLit ? 'observer_back_lit' : 'observer_back'),
      ]
    case 'slime_block':
      return all('slime')
    case 'redstone_block':
      return all('redstone_block')
    case 'iron_block':
      return all('iron_block')
    case 'light_blue_glazed_terracotta':
      return all('glazed_terracotta_light_blue')
    case 'glass':
      return all('glass')
  }
}
